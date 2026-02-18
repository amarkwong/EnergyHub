"""Energy plan and TOU ingestion service."""
from __future__ import annotations

import json
from datetime import date, datetime, time
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models.energy_plan import EnergyPlan, Retailer, TouDefinition, TouPeriod


ROOT = Path(__file__).resolve().parents[1]
RETAIL_PLANS_PATH = ROOT / "data" / "retail_plans.json"
NETWORK_TARIFFS_PATH = ROOT / "data" / "network_tariffs.json"


RETAILER_TIMEZONES = {
    "agl": "Australia/Sydney",
    "origin-energy": "Australia/Sydney",
    "energyaustralia": "Australia/Sydney",
}


RETAILER_TOU_OVERRIDES = {
    "agl": [
        {"name": "peak", "start_time": "15:00", "end_time": "21:00", "days": [0, 1, 2, 3, 4]},
        {"name": "shoulder", "start_time": "07:00", "end_time": "15:00", "days": [0, 1, 2, 3, 4]},
        {"name": "off_peak", "start_time": "21:00", "end_time": "07:00", "days": [0, 1, 2, 3, 4, 5, 6]},
    ],
    "origin-energy": [
        {"name": "peak", "start_time": "16:00", "end_time": "21:00", "days": [0, 1, 2, 3, 4]},
        {"name": "off_peak", "start_time": "21:00", "end_time": "16:00", "days": [0, 1, 2, 3, 4, 5, 6]},
    ],
    "energyaustralia": [
        {"name": "peak", "start_time": "14:00", "end_time": "20:00", "days": [0, 1, 2, 3, 4]},
        {"name": "shoulder", "start_time": "07:00", "end_time": "14:00", "days": [0, 1, 2, 3, 4]},
        {"name": "off_peak", "start_time": "20:00", "end_time": "07:00", "days": [0, 1, 2, 3, 4, 5, 6]},
    ],
}


NETWORK_PERIOD_WINDOWS = {
    "ausgrid": {
        "peak": ("14:00", "20:00", [0, 1, 2, 3, 4]),
        "shoulder": ("07:00", "14:00", [0, 1, 2, 3, 4]),
        "off_peak": ("20:00", "07:00", [0, 1, 2, 3, 4, 5, 6]),
    },
    "endeavour_energy": {
        "peak": ("13:00", "20:00", [0, 1, 2, 3, 4]),
        "shoulder": ("07:00", "13:00", [0, 1, 2, 3, 4]),
        "off_peak": ("20:00", "07:00", [0, 1, 2, 3, 4, 5, 6]),
    },
    "ausnet_services": {
        "peak": ("15:00", "21:00", [0, 1, 2, 3, 4]),
        "off_peak": ("21:00", "15:00", [0, 1, 2, 3, 4, 5, 6]),
    },
    "evoenergy": {
        "peak": ("17:00", "20:00", [0, 1, 2, 3, 4]),
        "off_peak": ("20:00", "17:00", [0, 1, 2, 3, 4, 5, 6]),
    },
}


NETWORK_TIMEZONES = {
    "evoenergy": "Australia/Sydney",
    "energex": "Australia/Brisbane",
    "ergon_energy": "Australia/Brisbane",
    "tasnetworks": "Australia/Hobart",
}


class EnergyPlanService:
    """Ingest and query plan/tou data stored in DB."""

    def __init__(self, retail_plans_path: Path = RETAIL_PLANS_PATH, network_tariffs_path: Path = NETWORK_TARIFFS_PATH):
        self.retail_plans_path = retail_plans_path
        self.network_tariffs_path = network_tariffs_path

    def refresh_catalogs(self, db: Session) -> dict:
        retail_payload = json.loads(self.retail_plans_path.read_text(encoding="utf-8"))
        network_payload = json.loads(self.network_tariffs_path.read_text(encoding="utf-8"))

        db.query(TouPeriod).delete()
        db.query(TouDefinition).delete()
        db.query(EnergyPlan).delete()
        db.query(Retailer).delete()
        db.commit()

        retailer_by_slug: dict[str, Retailer] = {}
        seen_plan_keys: set[tuple[str, str, str, str]] = set()
        plan_count = 0
        tou_def_count = 0
        tou_period_count = 0

        for item in retail_payload.get("plans", []):
            retailer_name = item["retailer"].strip()
            slug = self._slugify(retailer_name)

            # Derive distributor from geography data
            distributors = item.get("distributors") or []
            first_distributor = distributors[0] if distributors else None

            # Skip exact duplicates (same plan_name + tariff_type + distributor for same retailer)
            plan_key = (slug, item["plan_name"], item["tariff_type"], first_distributor or "")
            if plan_key in seen_plan_keys:
                continue
            seen_plan_keys.add(plan_key)

            retailer = retailer_by_slug.get(slug)
            if not retailer:
                retailer = Retailer(
                    name=retailer_name,
                    slug=slug,
                    source_url=item.get("source_url"),
                )
                db.add(retailer)
                db.flush()
                retailer_by_slug[slug] = retailer

            feed_in_tariffs = item.get("feed_in_tariffs") or []
            feed_in_rate = feed_in_tariffs[0]["unit_price_cents_per_kwh"] if feed_in_tariffs else None

            plan = EnergyPlan(
                retailer_id=retailer.id,
                plan_name=item["plan_name"],
                network_provider=first_distributor or item.get("network_provider"),
                tariff_type=item["tariff_type"],
                effective_from=date.fromisoformat(item["effective_from"]),
                effective_to=date.fromisoformat(item["effective_to"]) if item.get("effective_to") else None,
                daily_supply_charge_cents=item["daily_supply_charge_cents"],
                usage_rate_cents_per_kwh=item.get("usage_rate_cents_per_kwh"),
                feed_in_tariff_cents_per_kwh=feed_in_rate,
                feed_in_tariffs_json=json.dumps(feed_in_tariffs) if feed_in_tariffs else None,
                source_url=item.get("source_url"),
                is_active=True,
            )
            db.add(plan)
            db.flush()
            plan_count += 1

            definition = TouDefinition(
                scope_type="retailer",
                scope_key=slug,
                name=f"{retailer_name} {item['plan_name']}",
                timezone=RETAILER_TIMEZONES.get(slug, "Australia/Sydney"),
                source_url=item.get("source_url"),
                effective_from=plan.effective_from,
                effective_to=plan.effective_to,
                plan_id=plan.id,
            )
            db.add(definition)
            db.flush()
            tou_def_count += 1

            catalog_tou_rates = item.get("tou_rates") or []
            periods = self._retailer_periods_for_plan(slug, plan.tariff_type, item.get("usage_rate_cents_per_kwh"), catalog_tou_rates)
            for idx, period in enumerate(periods):
                db.add(
                    TouPeriod(
                        definition_id=definition.id,
                        name=period["name"],
                        start_time=self._parse_time(period["start_time"]),
                        end_time=self._parse_time(period["end_time"]),
                        days_of_week=self._days_to_csv(period["days"]),
                        rate_cents_per_kwh=period.get("rate_cents_per_kwh"),
                        demand_rate_cents_per_kva=period.get("demand_rate_cents_per_kva"),
                        unit=period.get("unit", "kWh"),
                        priority=idx + 1,
                    )
                )
                tou_period_count += 1

        for tariff in network_payload.get("tariffs", []):
            definition = TouDefinition(
                scope_type="network",
                scope_key=tariff["network_provider"],
                name=f"{tariff['network_provider']} {tariff['tariff_code']}",
                timezone=NETWORK_TIMEZONES.get(tariff["network_provider"], "Australia/Sydney"),
                source_url=tariff.get("source_url"),
                effective_from=date.fromisoformat(tariff["effective_from"]),
                effective_to=date.fromisoformat(tariff["effective_to"]) if tariff.get("effective_to") else None,
                plan_id=None,
            )
            db.add(definition)
            db.flush()
            tou_def_count += 1

            periods = self._network_periods_for_tariff(tariff)
            for idx, period in enumerate(periods):
                db.add(
                    TouPeriod(
                        definition_id=definition.id,
                        name=period["name"],
                        start_time=self._parse_time(period["start_time"]),
                        end_time=self._parse_time(period["end_time"]),
                        days_of_week=self._days_to_csv(period["days"]),
                        rate_cents_per_kwh=period.get("rate_cents_per_kwh"),
                        demand_rate_cents_per_kva=period.get("demand_rate_cents_per_kva"),
                        unit=period.get("unit", "kWh"),
                        priority=idx + 1,
                    )
                )
                tou_period_count += 1

        db.commit()
        return {
            "retailers": len(retailer_by_slug),
            "plans": plan_count,
            "tou_definitions": tou_def_count,
            "tou_periods": tou_period_count,
        }

    def list_retailers(self, db: Session) -> list[Retailer]:
        return db.query(Retailer).order_by(Retailer.name.asc()).all()

    def list_energy_plans(
        self,
        db: Session,
        retailer_slug: Optional[str] = None,
        network_provider: Optional[str] = None,
    ) -> list[EnergyPlan]:
        query = db.query(EnergyPlan).join(Retailer, Retailer.id == EnergyPlan.retailer_id)
        if retailer_slug:
            query = query.filter(Retailer.slug == retailer_slug)
        if network_provider:
            query = query.filter(EnergyPlan.network_provider == network_provider)
        return query.order_by(Retailer.name.asc(), EnergyPlan.plan_name.asc(), EnergyPlan.effective_from.desc()).all()

    def list_tou_definitions(
        self,
        db: Session,
        scope_type: Optional[str] = None,
        scope_key: Optional[str] = None,
    ) -> list[TouDefinition]:
        query = db.query(TouDefinition)
        if scope_type:
            query = query.filter(TouDefinition.scope_type == scope_type)
        if scope_key:
            query = query.filter(TouDefinition.scope_key == scope_key)
        return query.order_by(TouDefinition.scope_type.asc(), TouDefinition.scope_key.asc(), TouDefinition.effective_from.desc()).all()

    @staticmethod
    def _slugify(name: str) -> str:
        return "-".join(name.strip().lower().split())

    @staticmethod
    def _parse_time(raw: str) -> time:
        return datetime.strptime(raw, "%H:%M").time()

    @staticmethod
    def _days_to_csv(days: list[int]) -> str:
        return ",".join(str(d) for d in sorted(set(days)))

    def _retailer_periods_for_plan(
        self, retailer_slug: str, tariff_type: str, usage_rate: Optional[float], catalog_tou_rates: Optional[list[dict]] = None,
    ) -> list[dict]:
        # If the catalog carries per-period TOU rates from the CDR API, use them directly
        if tariff_type == "tou" and catalog_tou_rates:
            return self._merge_catalog_tou_rates(retailer_slug, catalog_tou_rates)

        if tariff_type == "tou":
            return self._attach_rate_defaults(RETAILER_TOU_OVERRIDES.get(retailer_slug, []), usage_rate)

        # Flat tariff plans always get a single "anytime" period
        return [
            {
                "name": "anytime",
                "start_time": "00:00",
                "end_time": "23:59",
                "days": [0, 1, 2, 3, 4, 5, 6],
                "rate_cents_per_kwh": usage_rate,
                "unit": "kWh",
            }
        ]

    def _merge_catalog_tou_rates(self, retailer_slug: str, catalog_tou_rates: list[dict]) -> list[dict]:
        """Build TOU periods from CDR-sourced tou_rates, falling back to override windows for time/days."""
        overrides = RETAILER_TOU_OVERRIDES.get(retailer_slug, [])
        override_by_name = {o["name"]: o for o in overrides}

        periods: list[dict] = []
        for entry in catalog_tou_rates:
            name = entry.get("name") or "unknown"
            rate = entry.get("rate_cents_per_kwh")

            # Use catalog time windows if present, otherwise fall back to retailer overrides
            override = override_by_name.get(name, {})
            start_time = entry.get("start_time") or override.get("start_time") or "00:00"
            end_time = entry.get("end_time") or override.get("end_time") or "23:59"
            days = entry.get("days") or override.get("days") or [0, 1, 2, 3, 4, 5, 6]

            periods.append({
                "name": name,
                "start_time": start_time,
                "end_time": end_time,
                "days": days,
                "rate_cents_per_kwh": rate,
                "unit": "kWh",
            })

        return periods if periods else self._attach_rate_defaults(overrides, None)

    def _network_periods_for_tariff(self, tariff: dict) -> list[dict]:
        if tariff.get("tariff_type") == "flat":
            return [
                {
                    "name": "anytime",
                    "start_time": "00:00",
                    "end_time": "23:59",
                    "days": [0, 1, 2, 3, 4, 5, 6],
                    "rate_cents_per_kwh": tariff.get("usage_rate_cents_per_kwh"),
                    "unit": "kWh",
                }
            ]

        from_tariff = tariff.get("time_periods") or []
        if from_tariff:
            windows = NETWORK_PERIOD_WINDOWS.get(tariff["network_provider"], {})
            periods = []
            for p in from_tariff:
                name = (p.get("name") or "").strip().lower()
                start_time, end_time, days = windows.get(name, ("00:00", "23:59", [0, 1, 2, 3, 4, 5, 6]))
                periods.append(
                    {
                        "name": name or "anytime",
                        "start_time": p.get("start_time", start_time),
                        "end_time": p.get("end_time", end_time),
                        "days": p.get("days", days),
                        "rate_cents_per_kwh": p.get("rate_cents_per_kwh"),
                        "unit": "kWh",
                    }
                )
            return periods

        return [
            {
                "name": "anytime",
                "start_time": "00:00",
                "end_time": "23:59",
                "days": [0, 1, 2, 3, 4, 5, 6],
                "rate_cents_per_kwh": tariff.get("usage_rate_cents_per_kwh"),
                "unit": "kWh",
            }
        ]

    @staticmethod
    def _attach_rate_defaults(periods: list[dict], base_rate: Optional[float]) -> list[dict]:
        if not periods:
            return [
                {
                    "name": "anytime",
                    "start_time": "00:00",
                    "end_time": "23:59",
                    "days": [0, 1, 2, 3, 4, 5, 6],
                    "rate_cents_per_kwh": base_rate,
                    "unit": "kWh",
                }
            ]

        adjusted: list[dict] = []
        for period in periods:
            name = period["name"]
            multiplier = 1.0
            if name == "peak":
                multiplier = 1.20
            elif name == "shoulder":
                multiplier = 1.0
            elif name == "off_peak":
                multiplier = 0.80

            rate = period.get("rate_cents_per_kwh")
            if rate is None and base_rate is not None:
                rate = round(float(base_rate) * multiplier, 4)

            adjusted.append(
                {
                    "name": name,
                    "start_time": period["start_time"],
                    "end_time": period["end_time"],
                    "days": period["days"],
                    "rate_cents_per_kwh": rate,
                    "unit": period.get("unit", "kWh"),
                }
            )
        return adjusted
