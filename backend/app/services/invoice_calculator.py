"""Invoice calculation service."""
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
import re
from typing import Optional

from app.services.nem12_service import NEM12Service
from app.services.providers.tariff_providers import (
    FeedInTariffComponent,
    JsonCatalogTariffProvider,
    TariffPeriod,
)


MONEY_QUANT = Decimal("0.01")


class InvoiceCalculator:
    """Service for calculating expected invoice from consumption and tariffs."""

    def __init__(self):
        self._nem12_service = NEM12Service()
        self._tariff_provider = JsonCatalogTariffProvider()

    async def calculate(
        self,
        nem12_file_id: str,
        network_tariff_code: Optional[str] = None,
        retail_plan_name: Optional[str] = None,
        billing_start: str = None,
        billing_end: str = None,
        parsed_invoice: Optional[dict] = None,
    ) -> dict:
        """Calculate expected invoice based on consumption and source-backed tariffs."""
        if parsed_invoice:
            return await self._calculate_from_invoice_context(
                nem12_file_id=nem12_file_id,
                parsed_invoice=parsed_invoice,
                network_tariff_code=network_tariff_code,
                retail_plan_name=retail_plan_name,
                billing_start=billing_start,
                billing_end=billing_end,
            )

        summaries = await self._nem12_service.get_consumption_summary(nem12_file_id)
        if not summaries:
            raise ValueError("No consumption data found for file ID")

        summary = summaries[0]
        if not network_tariff_code:
            raise ValueError("Network tariff code is required when invoice context is unavailable")
        network_tariff = await self._tariff_provider.get_tariff_by_code(network_tariff_code)
        if not network_tariff:
            raise ValueError(f"Unknown network tariff code: {network_tariff_code}")

        retail_plan = None
        if retail_plan_name:
            retail_plan = await self._tariff_provider.get_plan(retail_plan_name)
            if not retail_plan:
                raise ValueError(f"Unknown retail plan: {retail_plan_name}")

        if billing_start and billing_end:
            period_start = datetime.strptime(billing_start, "%Y-%m-%d").date()
            period_end = datetime.strptime(billing_end, "%Y-%m-%d").date()
        else:
            period_start = summary["period_start"]
            period_end = summary["period_end"]

        billing_days = (period_end - period_start).days + 1

        total_kwh = Decimal(str(summary["total_kwh"]))
        peak_kwh = Decimal(str(summary["peak_kwh"]))
        off_peak_kwh = Decimal(str(summary["off_peak_kwh"]))

        line_items: list[dict] = []

        network_daily = (network_tariff.daily_supply_charge_cents / 100).quantize(MONEY_QUANT)
        network_supply_amount = (network_daily * billing_days).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        line_items.append(
            {
                "description": "Network Daily Supply Charge",
                "charge_type": "network",
                "quantity": float(billing_days),
                "unit": "day",
                "rate": network_daily,
                "amount": network_supply_amount,
                "tariff_code": network_tariff_code,
                "period_start": period_start,
                "period_end": period_end,
            }
        )

        if retail_plan:
            retail_daily = (retail_plan.daily_supply_charge_cents / 100).quantize(MONEY_QUANT)
            retail_supply_amount = (retail_daily * billing_days).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
            line_items.append(
                {
                    "description": f"Retail Daily Supply Charge ({retail_plan.plan_name})",
                    "charge_type": "supply",
                    "quantity": float(billing_days),
                    "unit": "day",
                    "rate": retail_daily,
                    "amount": retail_supply_amount,
                    "period_start": period_start,
                    "period_end": period_end,
                }
            )

        if retail_plan:
            line_items.extend(self._build_usage_items_for_plan(retail_plan.time_periods, retail_plan.usage_rate_cents_per_kwh, peak_kwh, off_peak_kwh, total_kwh, "usage", f"Retail Energy ({retail_plan.plan_name})"))
            line_items.extend(self._build_usage_items_for_plan(network_tariff.time_periods, network_tariff.usage_rate_cents_per_kwh, peak_kwh, off_peak_kwh, total_kwh, "network", f"Network Usage ({network_tariff.tariff_code})"))
        else:
            # No retailer plan provided: calculate bill using only selected network tariff data.
            line_items.extend(self._build_usage_items_for_plan(network_tariff.time_periods, network_tariff.usage_rate_cents_per_kwh, peak_kwh, off_peak_kwh, total_kwh, "usage", "Energy Usage"))

        subtotal = sum(item["amount"] for item in line_items)
        gst = (subtotal * Decimal("0.10")).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        total = subtotal + gst

        note_parts = [
            f"Network tariff {network_tariff.tariff_code} from {network_tariff.source_url or 'catalog'}",
        ]
        if retail_plan:
            note_parts.append(f"Retail plan {retail_plan.plan_name} from {retail_plan.source_url or 'catalog'}")

        return {
            "nmi": summary["nmi"],
            "billing_period_start": period_start,
            "billing_period_end": period_end,
            "line_items": line_items,
            "subtotal": subtotal,
            "gst": gst,
            "total": total,
            "calculation_notes": " | ".join(note_parts),
        }

    def _build_usage_items_for_plan(
        self,
        time_periods: list[TariffPeriod],
        flat_rate_cents: Optional[Decimal],
        peak_kwh: Decimal,
        off_peak_kwh: Decimal,
        total_kwh: Decimal,
        charge_type: str,
        label_prefix: str,
    ) -> list[dict]:
        items: list[dict] = []

        if time_periods:
            peak_rate = self._find_period_rate(time_periods, "peak")
            off_peak_rate = self._find_period_rate(time_periods, "off_peak") or self._find_period_rate(time_periods, "shoulder")

            if peak_rate and peak_kwh > 0:
                amount = (peak_kwh * peak_rate / 100).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
                items.append(
                    {
                        "description": f"{label_prefix} Peak",
                        "charge_type": charge_type,
                        "quantity": float(peak_kwh),
                        "unit": "kWh",
                        "rate": (peak_rate / 100).quantize(MONEY_QUANT),
                        "amount": amount,
                    }
                )

            if off_peak_rate and off_peak_kwh > 0:
                amount = (off_peak_kwh * off_peak_rate / 100).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
                items.append(
                    {
                        "description": f"{label_prefix} Off-Peak",
                        "charge_type": charge_type,
                        "quantity": float(off_peak_kwh),
                        "unit": "kWh",
                        "rate": (off_peak_rate / 100).quantize(MONEY_QUANT),
                        "amount": amount,
                    }
                )
            return items

        effective_flat = flat_rate_cents or Decimal("0")
        if effective_flat <= 0:
            return items

        amount = (total_kwh * effective_flat / 100).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        items.append(
            {
                "description": label_prefix,
                "charge_type": charge_type,
                "quantity": float(total_kwh),
                "unit": "kWh",
                "rate": (effective_flat / 100).quantize(MONEY_QUANT),
                "amount": amount,
            }
        )
        return items

    def _find_period_rate(self, periods: list[TariffPeriod], period_name: str) -> Optional[Decimal]:
        for period in periods:
            if period.name.strip().lower() == period_name:
                return period.rate_cents_per_kwh
        return None

    async def _calculate_from_invoice_context(
        self,
        nem12_file_id: str,
        parsed_invoice: dict,
        network_tariff_code: Optional[str] = None,
        retail_plan_name: Optional[str] = None,
        billing_start: str = None,
        billing_end: str = None,
    ) -> dict:
        if billing_start and billing_end:
            period_start = datetime.strptime(billing_start, "%Y-%m-%d").date()
            period_end = datetime.strptime(billing_end, "%Y-%m-%d").date()
        else:
            period_start = parsed_invoice.get("billing_period_start")
            period_end = parsed_invoice.get("billing_period_end")
            if isinstance(period_start, str):
                period_start = datetime.strptime(period_start, "%Y-%m-%d").date()
            if isinstance(period_end, str):
                period_end = datetime.strptime(period_end, "%Y-%m-%d").date()
        if not period_start or not period_end:
            raise ValueError("Billing period is required for invoice-context calculation")

        billing_days = (period_end - period_start).days + 1
        start_str = period_start.isoformat()
        end_str = period_end.isoformat()
        intervals = await self._nem12_service.get_interval_data(
            file_id=nem12_file_id,
            nmi=parsed_invoice.get("nmi") if parsed_invoice.get("nmi") not in (None, "UNKNOWN") else None,
            start_date=start_str,
            end_date=end_str,
        )
        fallback_used_all_intervals = False
        if not intervals:
            intervals = await self._nem12_service.get_interval_data(
                file_id=nem12_file_id,
                nmi=parsed_invoice.get("nmi") if parsed_invoice.get("nmi") not in (None, "UNKNOWN") else None,
            )
            fallback_used_all_intervals = True
        if not intervals:
            raise ValueError("No interval data found for file ID")

        usage_buckets = self._summarize_intervals_for_invoice(intervals)
        retail_plan = None
        if retail_plan_name:
            retail_plan = await self._tariff_provider.get_plan(
                retail_plan_name,
                retailer=parsed_invoice.get("retailer"),
            )
            if not retail_plan:
                retail_plan = await self._tariff_provider.get_plan(retail_plan_name)

        feed_in_first_kwh, feed_in_next_kwh = self._compute_feed_in_split(
            total_export_kwh=usage_buckets["solar_export"],
            billing_days=billing_days,
            components=retail_plan.feed_in_tariffs if retail_plan else [],
        )
        if feed_in_next_kwh <= 0:
            inv_first_kwh, inv_next_kwh = self._extract_feed_in_split_from_invoice(
                parsed_invoice.get("line_items", []),
                usage_buckets["solar_export"],
            )
            if inv_next_kwh > 0:
                feed_in_first_kwh, feed_in_next_kwh = inv_first_kwh, inv_next_kwh

        line_items: list[dict] = []
        taxable_subtotal = Decimal("0")
        has_any_non_gst = False

        for inv_item in parsed_invoice.get("line_items", []):
            desc = str(inv_item.get("description", "")).strip()
            charge_type = inv_item.get("charge_type", "other")
            if charge_type == "gst":
                continue

            qty, unit = self._resolve_quantity_for_description(
                desc,
                inv_item.get("quantity"),
                inv_item.get("unit"),
                billing_days,
                usage_buckets,
                feed_in_first_kwh,
                feed_in_next_kwh,
            )
            rate_raw = inv_item.get("rate")
            rate = Decimal(str(rate_raw)) if rate_raw is not None else None
            if rate is not None and qty is not None:
                amount = (qty * rate).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
            else:
                amount = Decimal(str(inv_item.get("amount", 0)))

            line_items.append(
                {
                    "description": desc,
                    "charge_type": charge_type,
                    "quantity": float(qty) if qty is not None else inv_item.get("quantity"),
                    "unit": unit,
                    "rate": rate,
                    "amount": amount,
                    "tariff_code": inv_item.get("tariff_code"),
                    "period_start": period_start,
                    "period_end": period_end,
                }
            )
            has_any_non_gst = True
            if not self._is_gst_exempt_description(desc):
                taxable_subtotal += amount

        if not has_any_non_gst:
            # Fallback to catalog path if parsed invoice had no usable line items.
            return await self.calculate(
                nem12_file_id=nem12_file_id,
                network_tariff_code=network_tariff_code,
                retail_plan_name=retail_plan_name,
                billing_start=start_str,
                billing_end=end_str,
                parsed_invoice=None,
            )

        gst_amount = (taxable_subtotal * Decimal("0.10")).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        gst_source_item = next((i for i in parsed_invoice.get("line_items", []) if i.get("charge_type") == "gst"), None)
        gst_description = gst_source_item.get("description") if gst_source_item else "GST"
        line_items.append(
            {
                "description": gst_description,
                "charge_type": "gst",
                "quantity": None,
                "unit": None,
                "rate": None,
                "amount": gst_amount,
                "period_start": period_start,
                "period_end": period_end,
            }
        )

        subtotal = sum(item["amount"] for item in line_items if item["charge_type"] != "gst")
        total = subtotal + gst_amount

        note_parts = ["Calculated from invoice-extracted line items and interval usage."]
        if parsed_invoice.get("energy_plan_name"):
            note_parts.append(f"Invoice plan: {parsed_invoice['energy_plan_name']}")
        if parsed_invoice.get("network_provider"):
            note_parts.append(f"Network provider: {parsed_invoice['network_provider']}")
        if network_tariff_code:
            note_parts.append(f"User-selected tariff input: {network_tariff_code}")
        if retail_plan_name:
            note_parts.append(f"User-selected plan input: {retail_plan_name}")
        if fallback_used_all_intervals:
            note_parts.append("Warning: no interval overlap with invoice billing period; used all available intervals.")

        return {
            "nmi": parsed_invoice.get("nmi") or intervals[0].get("nmi") or "Unknown",
            "billing_period_start": period_start,
            "billing_period_end": period_end,
            "line_items": line_items,
            "subtotal": subtotal,
            "gst": gst_amount,
            "total": total,
            "calculation_notes": " | ".join(note_parts),
        }

    @staticmethod
    def _summarize_intervals_for_invoice(intervals: list[dict]) -> dict[str, Decimal]:
        general = Decimal("0")
        controlled = Decimal("0")
        solar_export = Decimal("0")
        for row in intervals:
            value = Decimal(str(row.get("value", 0)))
            rate_desc = str(row.get("rate_type_description") or "").lower()
            reg = str(row.get("register_code") or "").lower()
            if "solar" in rate_desc or "#b" in reg:
                solar_export += value
            elif "controlled" in rate_desc or "cl" in rate_desc or "#e2" in reg:
                controlled += value
            else:
                general += value
        return {
            "general": general,
            "controlled": controlled,
            "solar_export": solar_export,
            "total_import": general + controlled,
        }

    @staticmethod
    def _resolve_quantity_for_description(
        description: str,
        invoice_quantity: Optional[float],
        invoice_unit: Optional[str],
        billing_days: int,
        usage_buckets: dict[str, Decimal],
        feed_in_first_kwh: Decimal,
        feed_in_next_kwh: Decimal,
    ) -> tuple[Optional[Decimal], Optional[str]]:
        desc = description.lower()
        if desc.startswith("next"):
            if feed_in_next_kwh > 0:
                return -feed_in_next_kwh, "kWh"
            if invoice_quantity is not None:
                return -abs(Decimal(str(invoice_quantity))), "kWh"
            return Decimal("0"), "kWh"
        if "feed-in" in desc:
            if feed_in_next_kwh > 0 and ("standard" in desc or "first" in desc):
                return -feed_in_first_kwh, "kWh"
            if usage_buckets["solar_export"] > 0:
                return -usage_buckets["solar_export"], "kWh"
            if invoice_quantity is not None:
                return -abs(Decimal(str(invoice_quantity))), "kWh"
            return Decimal("0"), "kWh"
        if "fit policy" in desc:
            if usage_buckets["solar_export"] > 0:
                return -usage_buckets["solar_export"], "kWh"
            if invoice_quantity is not None:
                return -abs(Decimal(str(invoice_quantity))), "kWh"
            return Decimal("0"), "kWh"
        if "controlled load" in desc or "tariff 31" in desc or "cl31" in desc:
            if usage_buckets["controlled"] > 0 or invoice_quantity is None:
                return usage_buckets["controlled"], "kWh"
            return Decimal(str(invoice_quantity)), "kWh"
        if "general usage" in desc or "usage" in desc:
            if usage_buckets["general"] > 0 or invoice_quantity is None:
                return usage_buckets["general"], "kWh"
            return Decimal(str(invoice_quantity)), "kWh"
        if "supply charge" in desc:
            return Decimal(str(invoice_quantity)) if invoice_quantity is not None else Decimal(billing_days), "day"
        if invoice_quantity is not None:
            return Decimal(str(invoice_quantity)), invoice_unit
        return None, invoice_unit

    @staticmethod
    def _is_gst_exempt_description(description: str) -> bool:
        desc = description.lower()
        return "feed-in" in desc or desc.startswith("next")

    @staticmethod
    def _compute_feed_in_split(
        total_export_kwh: Decimal,
        billing_days: int,
        components: list[FeedInTariffComponent],
    ) -> tuple[Decimal, Decimal]:
        if total_export_kwh <= 0:
            return Decimal("0"), Decimal("0")

        if len(components) < 2:
            return total_export_kwh, Decimal("0")

        first_tier_daily_cap = InvoiceCalculator._extract_first_tier_daily_cap(components)
        if first_tier_daily_cap is None or first_tier_daily_cap <= 0:
            return total_export_kwh, Decimal("0")

        cap_for_period = first_tier_daily_cap * Decimal(str(max(billing_days, 1)))
        first_kwh = total_export_kwh if total_export_kwh <= cap_for_period else cap_for_period
        next_kwh = total_export_kwh - first_kwh
        return first_kwh, next_kwh

    @staticmethod
    def _extract_first_tier_daily_cap(components: list[FeedInTariffComponent]) -> Optional[Decimal]:
        for comp in components:
            if comp.tier_min_kwh == Decimal("0") and comp.tier_max_kwh is not None:
                return comp.tier_max_kwh

        for comp in components:
            name = (comp.name or "").lower()
            match = re.search(r"first\s+(\d+(?:\.\d+)?)\s*kwh", name)
            if match:
                return Decimal(match.group(1))

        return None

    @staticmethod
    def _extract_feed_in_split_from_invoice(
        invoice_items: list[dict],
        total_export_kwh: Decimal,
    ) -> tuple[Decimal, Decimal]:
        first_qty: Optional[Decimal] = None
        next_qty: Optional[Decimal] = None

        for item in invoice_items:
            desc = str(item.get("description", "")).strip().lower()
            qty_raw = item.get("quantity")
            if qty_raw is None:
                continue
            qty = abs(Decimal(str(qty_raw)))
            if qty <= 0:
                continue
            if desc.startswith("next"):
                next_qty = qty
                continue
            if "feed-in" in desc and ("standard" in desc or "first" in desc):
                first_qty = qty

        if first_qty is not None and next_qty is not None:
            return first_qty, next_qty
        if first_qty is not None:
            next_derived = total_export_kwh - first_qty
            return first_qty, next_derived if next_derived > 0 else Decimal("0")
        if next_qty is not None:
            first_derived = total_export_kwh - next_qty
            return first_derived if first_derived > 0 else Decimal("0"), next_qty
        return total_export_kwh, Decimal("0")
