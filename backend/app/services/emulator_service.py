"""Plan emulator: compare all retail plans against actual meter data."""
from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from app.db.database import SessionLocal
from app.models.invoice import Invoice
from app.models.meter_data import MeterDataInterval
from app.services.catalog_service import get_catalog
from app.services.energy_expert_service import EnergyExpertService

MONEY_QUANT = Decimal("0.01")


def _slugify(name: str) -> str:
    return "-".join(name.strip().lower().split())


def _parse_hour(raw: str) -> int:
    """Parse 'HH:MM' to integer hour."""
    return int(raw.split(":")[0])


def _parse_end_hour(raw: str) -> int:
    """Parse end time: round up if minutes > 0 (handles CDR ':59' format)."""
    parts = raw.split(":")
    hour = int(parts[0])
    minutes = int(parts[1]) if len(parts) > 1 else 0
    return hour + 1 if minutes > 0 else hour


def _is_within_period(hour: int, start: int, end: int) -> bool:
    if start == end:
        return True
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


class EmulatorService:
    """Compare all retail plans against actual interval meter data."""

    def _load_plan_catalog(self) -> list[dict]:
        return get_catalog().get_all_plans()

    def _filter_plans_by_postcode(self, catalog: list[dict], postcode: Optional[str]) -> list[dict]:
        """Use catalog's postcode index for O(1) lookup."""
        if not postcode:
            return catalog
        return get_catalog().get_plans_for_postcode(postcode)

    async def compare_plans(
        self,
        nmi: str,
        billing_start: date,
        billing_end: date,
        user_id: int,
        retailer_filter: Optional[list[str]] = None,
        postcode: Optional[str] = None,
    ) -> dict:
        # 1. Load intervals from DB
        intervals = self._load_intervals(nmi, billing_start, billing_end)
        if not intervals:
            raise ValueError(
                f"No meter data found for NMI {nmi} between {billing_start} and {billing_end}"
            )

        billing_days = (billing_end - billing_start).days + 1

        # 2. Classify intervals into import vs export
        import_intervals, export_intervals = self._classify_intervals(intervals)
        total_import_kwh = sum(iv["value"] for iv in import_intervals)
        total_export_kwh = sum(iv["value"] for iv in export_intervals)

        # 3. Load plan catalog, filter by postcode and retailer
        if postcode:
            catalog = self._filter_plans_by_postcode([], postcode)
        else:
            catalog = self._load_plan_catalog()

        if retailer_filter:
            filter_set = {s.lower() for s in retailer_filter}
            catalog = [p for p in catalog if p.get("retailer_slug", _slugify(p.get("retailer", ""))) in filter_set]

        plan_results: list[dict] = []
        for plan in catalog:
            result = self._compute_plan_cost(
                plan, billing_days, import_intervals, total_import_kwh, total_export_kwh
            )
            plan_results.append(result)

        # 4. Sort by total ascending, assign ranks
        plan_results.sort(key=lambda r: r["total_dollars"])
        for idx, result in enumerate(plan_results):
            result["rank"] = idx + 1

        # 5. Look up actual invoiced total for this NMI + period
        invoiced_total = self._get_invoiced_total(user_id, nmi, billing_start, billing_end)
        current_total: Optional[Decimal] = None
        if invoiced_total is not None:
            current_total = Decimal(str(invoiced_total))

        # 6. Compute deltas vs invoiced total
        for result in plan_results:
            if current_total is not None:
                delta = result["total_dollars"] - current_total
                result["delta_vs_current_dollars"] = float(delta.quantize(MONEY_QUANT))
                if current_total != 0:
                    result["delta_vs_current_percent"] = float(
                        (delta / current_total * 100).quantize(Decimal("0.1"))
                    )
                else:
                    result["delta_vs_current_percent"] = None
            else:
                result["delta_vs_current_dollars"] = None
                result["delta_vs_current_percent"] = None

        cheapest = plan_results[0] if plan_results else None
        potential_annual_saving = None
        if cheapest and current_total is not None and billing_days > 0:
            saving_per_day = (current_total - cheapest["total_dollars"]) / billing_days
            potential_annual_saving = float((saving_per_day * 365).quantize(MONEY_QUANT))

        return {
            "nmi": nmi,
            "billing_start": billing_start,
            "billing_end": billing_end,
            "billing_days": billing_days,
            "total_import_kwh": float(Decimal(str(total_import_kwh)).quantize(Decimal("0.001"))),
            "total_export_kwh": float(Decimal(str(total_export_kwh)).quantize(Decimal("0.001"))),
            "interval_count": len(intervals),
            "invoiced_total": invoiced_total,
            "plans": [self._format_plan_result(r) for r in plan_results],
            "cheapest_plan_name": cheapest["plan_name"] if cheapest else "",
            "cheapest_total": float(cheapest["total_dollars"].quantize(MONEY_QUANT)) if cheapest else 0,
            "potential_annual_saving": potential_annual_saving,
        }

    @staticmethod
    def _get_invoiced_total(user_id: int, nmi: str, billing_start: date, billing_end: date) -> Optional[float]:
        """Sum the total from invoices matching the NMI and overlapping the billing period."""
        with SessionLocal() as db:
            invoices = (
                db.query(Invoice)
                .filter(
                    Invoice.user_id == user_id,
                    Invoice.nmi == nmi,
                    Invoice.billing_period_start.isnot(None),
                    Invoice.billing_period_end.isnot(None),
                    Invoice.total.isnot(None),
                )
                .order_by(Invoice.created_at.desc())
                .all()
            )
            if not invoices:
                return None

            # Deduplicate by (billing_period_start, billing_period_end) — keep latest
            seen: set[tuple[str, str]] = set()
            deduped: list[Invoice] = []
            for inv in invoices:
                key = (inv.billing_period_start or "", inv.billing_period_end or "")
                if key not in seen:
                    seen.add(key)
                    deduped.append(inv)

            # Filter to invoices whose billing period overlaps the emulation period
            bs = billing_start.isoformat()
            be = billing_end.isoformat()
            overlapping = [
                inv for inv in deduped
                if inv.billing_period_start <= be and inv.billing_period_end >= bs
            ]

            if not overlapping:
                return None

            return round(sum(float(inv.total) for inv in overlapping), 2)

    def _load_intervals(self, nmi: str, start: date, end: date) -> list[dict]:
        with SessionLocal() as db:
            rows = (
                db.query(MeterDataInterval)
                .filter(
                    MeterDataInterval.nmi == nmi,
                    MeterDataInterval.start_at >= datetime.combine(start, time.min),
                    MeterDataInterval.start_at <= datetime.combine(end, time.max),
                )
                .order_by(MeterDataInterval.start_at.asc())
                .all()
            )
            # Deduplicate: CDR imports can create multiple identical rows
            # for the same (register_code, start_at). Keep one per slot.
            seen: set[tuple[str, datetime]] = set()
            intervals: list[dict] = []
            for row in rows:
                key = (row.register_code, row.start_at)
                if key in seen:
                    continue
                seen.add(key)
                intervals.append({
                    "date": row.start_at.date(),
                    "hour": row.start_at.hour,
                    "minute": row.start_at.minute,
                    "weekday": row.start_at.weekday(),
                    "value": float(row.profile_read_value),
                    "interval_length_minutes": row.interval_length_minutes,
                    "register_code": row.register_code,
                    "rate_type_description": row.rate_type_description,
                })
            return intervals

    @staticmethod
    def _classify_intervals(intervals: list[dict]) -> tuple[list[dict], list[dict]]:
        imports = []
        exports = []
        for iv in intervals:
            rate_desc = (iv.get("rate_type_description") or "").lower()
            reg = (iv.get("register_code") or "").lower()
            if "solar" in rate_desc or "#b" in reg:
                exports.append(iv)
            else:
                imports.append(iv)
        return imports, exports

    def _compute_plan_cost(
        self,
        plan: dict,
        billing_days: int,
        import_intervals: list[dict],
        total_import_kwh: float,
        total_export_kwh: float,
    ) -> dict:
        retailer_slug = plan.get("retailer_slug", _slugify(plan.get("retailer", "")))

        # Supply charge
        daily_supply_cents = Decimal(str(plan.get("daily_supply_charge_cents", 0)))
        supply_charge = (daily_supply_cents * billing_days / 100).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)

        # Usage charge + period breakdown
        tou_rates = plan.get("tou_rates") or []
        tariff_type = plan.get("tariff_type", "flat")
        usage_rate = plan.get("usage_rate_cents_per_kwh")

        if tariff_type == "tou" and tou_rates:
            usage_charge, period_breakdown = self._compute_tou_usage(
                import_intervals, tou_rates, usage_rate
            )
        else:
            usage_charge, period_breakdown = self._compute_flat_usage(total_import_kwh, usage_rate)

        # Feed-in credit
        feed_in_tariffs = plan.get("feed_in_tariffs") or []
        feed_in_credit, feed_in_rate = self._compute_feed_in(
            total_export_kwh, billing_days, feed_in_tariffs
        )

        # GST: 10% on supply + usage, NOT on feed-in
        taxable = supply_charge + usage_charge
        gst = (taxable * Decimal("0.10")).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)

        subtotal = supply_charge + usage_charge - feed_in_credit
        total = subtotal + gst

        distributors = plan.get("distributors") or []
        return {
            "retailer": plan.get("retailer", retailer_slug),
            "retailer_slug": retailer_slug,
            "plan_name": plan.get("plan_name", ""),
            "tariff_type": tariff_type,
            "distributor": distributors[0] if distributors else None,
            "state": plan.get("state"),
            "supply_charge_dollars": supply_charge,
            "usage_charge_dollars": usage_charge,
            "feed_in_credit_dollars": feed_in_credit,
            "subtotal_dollars": subtotal,
            "gst_dollars": gst,
            "total_dollars": total,
            "period_breakdown": period_breakdown,
            "feed_in_rate_cents": feed_in_rate,
            "feed_in_kwh": total_export_kwh,
        }

    def _compute_tou_usage(
        self,
        import_intervals: list[dict],
        tou_rates: list[dict],
        fallback_rate: Optional[float],
    ) -> tuple[Decimal, list[dict]]:
        # Bucket usage by period name
        period_kwh: dict[str, Decimal] = {}
        period_rate: dict[str, Decimal] = {}

        fallback = Decimal(str(fallback_rate)) if fallback_rate is not None else Decimal("0")

        for iv in import_intervals:
            hour = iv["hour"]
            weekday = iv["weekday"]
            matched_name = None
            matched_rate = fallback

            for window in tou_rates:
                start = _parse_hour(window.get("start_time", "00:00"))
                end = _parse_end_hour(window.get("end_time", "23:59"))
                days = window.get("days", [0, 1, 2, 3, 4, 5, 6])
                if weekday in days and _is_within_period(hour, start, end):
                    matched_name = window.get("name", "usage")
                    rate_val = window.get("rate_cents_per_kwh")
                    if rate_val is not None:
                        matched_rate = Decimal(str(rate_val))
                    break

            if matched_name is None:
                matched_name = "usage"
                matched_rate = fallback

            period_kwh[matched_name] = period_kwh.get(matched_name, Decimal("0")) + Decimal(str(iv["value"]))
            period_rate[matched_name] = matched_rate

        breakdown = []
        total_usage = Decimal("0")
        for name in sorted(period_kwh.keys()):
            kwh = period_kwh[name]
            rate = period_rate[name]
            cost = (kwh * rate / 100).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
            total_usage += cost
            breakdown.append({
                "period_name": name,
                "kwh": float(kwh.quantize(Decimal("0.001"))),
                "rate_cents_per_kwh": float(rate.quantize(Decimal("0.01"))),
                "cost_dollars": float(cost),
            })

        return total_usage, breakdown

    @staticmethod
    def _compute_flat_usage(
        total_import_kwh: float, usage_rate: Optional[float]
    ) -> tuple[Decimal, list[dict]]:
        if usage_rate is None or usage_rate <= 0:
            return Decimal("0"), []

        rate = Decimal(str(usage_rate))
        kwh = Decimal(str(total_import_kwh))
        cost = (kwh * rate / 100).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        breakdown = [{
            "period_name": "usage",
            "kwh": float(kwh.quantize(Decimal("0.001"))),
            "rate_cents_per_kwh": float(rate.quantize(Decimal("0.01"))),
            "cost_dollars": float(cost),
        }]
        return cost, breakdown

    @staticmethod
    def _compute_feed_in(
        total_export_kwh: float,
        billing_days: int,
        feed_in_tariffs: list[dict],
    ) -> tuple[Decimal, Optional[float]]:
        if total_export_kwh <= 0 or not feed_in_tariffs:
            return Decimal("0"), None

        # Filter out legacy government FiT schemes
        retailer_fits = EnergyExpertService.filter_retail_feed_in_tariffs(feed_in_tariffs)
        if not retailer_fits:
            return Decimal("0"), None

        export_kwh = Decimal(str(total_export_kwh))

        if len(retailer_fits) == 1:
            rate = Decimal(str(retailer_fits[0]["unit_price_cents_per_kwh"]))
            credit = (export_kwh * rate / 100).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
            return credit, float(rate)

        # Multi-tier: first tier has a daily cap
        first_tier = retailer_fits[0]
        first_rate = Decimal(str(first_tier["unit_price_cents_per_kwh"]))
        daily_cap = first_tier.get("tier_max_kwh")
        if daily_cap is not None:
            cap = Decimal(str(daily_cap)) * max(billing_days, 1)
            first_kwh = min(export_kwh, cap)
        else:
            first_kwh = export_kwh

        credit = (first_kwh * first_rate / 100).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        remaining = export_kwh - first_kwh

        if remaining > 0 and len(retailer_fits) > 1:
            next_rate = Decimal(str(retailer_fits[1]["unit_price_cents_per_kwh"]))
            credit += (remaining * next_rate / 100).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)

        return credit, float(first_rate)

    @staticmethod
    def _format_plan_result(result: dict) -> dict:
        """Convert Decimals to floats for JSON serialization."""
        return {
            "retailer": result["retailer"],
            "retailer_slug": result["retailer_slug"],
            "plan_name": result["plan_name"],
            "tariff_type": result["tariff_type"],
            "distributor": result.get("distributor"),
            "state": result.get("state"),
            "supply_charge_dollars": float(result["supply_charge_dollars"]),
            "usage_charge_dollars": float(result["usage_charge_dollars"]),
            "feed_in_credit_dollars": float(result["feed_in_credit_dollars"]),
            "subtotal_dollars": float(result["subtotal_dollars"]),
            "gst_dollars": float(result["gst_dollars"]),
            "total_dollars": float(result["total_dollars"]),
            "period_breakdown": result["period_breakdown"],
            "feed_in_rate_cents": result["feed_in_rate_cents"],
            "feed_in_kwh": result["feed_in_kwh"],
            "delta_vs_current_dollars": result["delta_vs_current_dollars"],
            "delta_vs_current_percent": result["delta_vs_current_percent"],
            "rank": result["rank"],
        }
