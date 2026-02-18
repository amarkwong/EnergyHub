"""Service for fetching retailer plans from EME CDR and persisting snapshots."""
from __future__ import annotations

import json
import re
from html import unescape
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib import request as urllib_request

from scripts.fetch_eme_plans import DEFAULT_BASE_URL, fetch_retailer_plans
from app.services.energy_expert_service import EnergyExpertService


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EME_OUTPUT_PATH = ROOT / "data" / "eme_plans_full.json"
DEFAULT_RETAIL_CATALOG_PATH = ROOT / "data" / "retail_plans.json"

SEMIANNUAL_EVENTBRIDGE_CRON = "cron(0 2 1 1,7 ? *)"

_NONE_OPTION = "none/not sure/not in this list"

RETAILER_SLUG_OVERRIDES = {
    "1st Energy": "1stenergy",
    "ActewAGL": "actewagl",
    "AGL": "agl",
    "Alinta Energy": "alinta",
    "Dodo": "dodo",
    "EnergyAustralia": "energyaustralia",
    "ENGIE - formerly Simply Energy": "simplyenergy",
    "Lumo Energy": "lumo",
    "Origin Energy": "origin",
    "OVO Energy": "ovo",
    "Powershop": "powershop",
    "Red Energy": "redenergy",
    "Simply Energy": "simplyenergy",
}


class EmePlanFetchService:
    """Fetch plans from EME API and write normalized snapshots."""

    def fetch_to_file(
        self,
        *,
        retailers: list[str],
        output_path: Path = DEFAULT_EME_OUTPUT_PATH,
        base_url: str = DEFAULT_BASE_URL,
        page_size: int = 20,
        max_plans: int = 0,
        fuel_type: str = "ELECTRICITY",
        timeout_seconds: float = 30.0,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "metadata": {
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "source": "AER CDR Energy Product Reference Data API",
                "base_url": base_url,
                "retailers": retailers,
                "fuel_type": fuel_type,
                "schedule": {
                    "cadence": "semiannual",
                    "months_interval": 6,
                    "eventbridge_cron": SEMIANNUAL_EVENTBRIDGE_CRON,
                    "next_recommended_run_utc": self.next_semiannual_run_utc().isoformat(),
                },
            },
            "plans": [],
            "stats": {},
        }

        seen_plan_keys: set[tuple] = set()
        for retailer in retailers:
            plans, stats = fetch_retailer_plans(
                base_url=base_url,
                retailer_slug=retailer,
                page_size=page_size,
                max_plans=max_plans,
                fuel_type=fuel_type,
                timeout_seconds=timeout_seconds,
            )
            unique_plans: list[dict[str, Any]] = []
            for plan in plans:
                key = self._plan_dedup_key(plan)
                if key in seen_plan_keys:
                    continue
                seen_plan_keys.add(key)
                unique_plans.append(plan)
            payload["plans"].extend(unique_plans)
            payload["stats"][retailer] = {
                **stats,
                "plans_normalized": len(plans),
                "plans_written": len(unique_plans),
            }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    def fetch_from_dropdown_html(
        self,
        *,
        dropdown_html: str,
        source_url: str,
        output_path: Path = DEFAULT_EME_OUTPUT_PATH,
        page_size: int = 20,
        max_plans: int = 0,
        fuel_type: str = "ELECTRICITY",
        timeout_seconds: float = 30.0,
    ) -> dict[str, Any]:
        retailer_names = self.extract_retailer_names(dropdown_html)
        payload: dict[str, Any] = {
            "metadata": {
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "source": "AER CDR Energy Product Reference Data API",
                "source_url": source_url,
                "fuel_type": fuel_type,
                "schedule": {
                    "cadence": "semiannual",
                    "months_interval": 6,
                    "eventbridge_cron": SEMIANNUAL_EVENTBRIDGE_CRON,
                    "next_recommended_run_utc": self.next_semiannual_run_utc().isoformat(),
                },
                "retailers_discovered": len(retailer_names),
            },
            "plans": [],
            "stats": {},
            "resolved_retailers": [],
            "unresolved_retailers": [],
        }

        seen_plan_keys: set[tuple] = set()
        fetched_slugs: set[str] = set()
        for retailer_name in retailer_names:
            slug_candidates = self.slug_candidates_for_name(retailer_name)
            resolved_slug = None
            errors: list[str] = []

            for slug in slug_candidates:
                if slug in fetched_slugs:
                    resolved_slug = slug
                    break
                try:
                    plans, stats = fetch_retailer_plans(
                        base_url=DEFAULT_BASE_URL,
                        retailer_slug=slug,
                        page_size=page_size,
                        max_plans=max_plans,
                        fuel_type=fuel_type,
                        timeout_seconds=timeout_seconds,
                    )
                    unique_plans: list[dict[str, Any]] = []
                    for plan in plans:
                        key = self._plan_dedup_key(plan)
                        if key in seen_plan_keys:
                            continue
                        seen_plan_keys.add(key)
                        plan["retailer_display_name"] = retailer_name
                        unique_plans.append(plan)
                    payload["plans"].extend(unique_plans)
                    payload["stats"][slug] = {
                        **stats,
                        "retailer_name": retailer_name,
                        "plans_normalized": len(plans),
                        "plans_written": len(unique_plans),
                    }
                    resolved_slug = slug
                    fetched_slugs.add(slug)
                    break
                except Exception as exc:
                    errors.append(f"{slug}: {exc}")

            if resolved_slug:
                payload["resolved_retailers"].append(
                    {"retailer_name": retailer_name, "retailer_slug": resolved_slug}
                )
            else:
                payload["unresolved_retailers"].append(
                    {
                        "retailer_name": retailer_name,
                        "slug_candidates": slug_candidates,
                        "errors": errors[:3],
                    }
                )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    def fetch_from_registry(
        self,
        *,
        registry_url: str,
        output_path: Path = DEFAULT_EME_OUTPUT_PATH,
        page_size: int = 20,
        max_plans: int = 0,
        fuel_type: str = "ELECTRICITY",
        timeout_seconds: float = 30.0,
    ) -> dict[str, Any]:
        """Fetch plans for all CDR-registered retailers discovered from the jxeeno registry."""
        registry_entries = self._download_registry(registry_url, timeout_seconds)

        payload: dict[str, Any] = {
            "metadata": {
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "source": "AER CDR Energy Product Reference Data API",
                "registry_url": registry_url,
                "fuel_type": fuel_type,
                "schedule": {
                    "cadence": "semiannual",
                    "months_interval": 6,
                    "eventbridge_cron": SEMIANNUAL_EVENTBRIDGE_CRON,
                    "next_recommended_run_utc": self.next_semiannual_run_utc().isoformat(),
                },
                "retailers_discovered": len(registry_entries),
            },
            "plans": [],
            "stats": {},
            "resolved_retailers": [],
            "unresolved_retailers": [],
        }

        seen_plan_keys: set[tuple] = set()
        fetched_slugs: set[str] = set()
        for entry in registry_entries:
            brand_name = entry["brand_name"]
            slug = entry["slug"]

            if slug in fetched_slugs:
                payload["resolved_retailers"].append(
                    {"retailer_name": brand_name, "retailer_slug": slug}
                )
                continue

            try:
                plans, stats = fetch_retailer_plans(
                    base_url=DEFAULT_BASE_URL,
                    retailer_slug=slug,
                    page_size=page_size,
                    max_plans=max_plans,
                    fuel_type=fuel_type,
                    timeout_seconds=timeout_seconds,
                )
                unique_plans: list[dict[str, Any]] = []
                for plan in plans:
                    key = self._plan_dedup_key(plan)
                    if key in seen_plan_keys:
                        continue
                    seen_plan_keys.add(key)
                    plan["retailer_display_name"] = brand_name
                    unique_plans.append(plan)
                payload["plans"].extend(unique_plans)
                payload["stats"][slug] = {
                    **stats,
                    "retailer_name": brand_name,
                    "plans_normalized": len(plans),
                    "plans_written": len(unique_plans),
                }
                fetched_slugs.add(slug)
                payload["resolved_retailers"].append(
                    {"retailer_name": brand_name, "retailer_slug": slug}
                )
            except Exception as exc:
                payload["unresolved_retailers"].append(
                    {
                        "retailer_name": brand_name,
                        "slug_candidates": [slug],
                        "errors": [f"{slug}: {exc}"],
                    }
                )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    @staticmethod
    def _download_registry(registry_url: str, timeout_seconds: float) -> list[dict[str, str]]:
        """Download the jxeeno CDR registry JSON and return energy retailer entries."""
        req = urllib_request.Request(registry_url, headers={"Accept": "application/json"})
        with urllib_request.urlopen(req, timeout=timeout_seconds) as resp:
            raw = json.loads(resp.read().decode("utf-8"))

        # Registry shape is {"data": [...]}}
        items = raw.get("data", []) if isinstance(raw, dict) else raw

        entries: list[dict[str, str]] = []
        for item in items:
            # Filter to energy data holders
            industries = item.get("industries") or []
            if not any("energy" in ind.lower() for ind in industries):
                continue

            base_uri = item.get("productReferenceDataBaseUri") or ""
            # Extract slug from URI like https://cdr.energymadeeasy.gov.au/<slug>
            slug = base_uri.rstrip("/").rsplit("/", 1)[-1] if base_uri else ""
            if not slug:
                continue

            brand_name = item.get("brandName") or slug
            entries.append({
                "brand_name": brand_name,
                "slug": slug,
                "base_uri": base_uri,
            })

        return entries

    def build_retail_catalog_payload(self, eme_payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
        today_iso = date.today().isoformat()
        plans_out: list[dict[str, Any]] = []
        skipped_missing_fields = 0
        dedup_dropped = 0
        seen_keys: set[tuple] = set()

        for plan in eme_payload.get("plans", []):
            if not isinstance(plan, dict):
                skipped_missing_fields += 1
                continue

            retailer = str(plan.get("retailer", "")).strip()
            plan_name = str(plan.get("plan_name", "")).strip()
            tariff_type = str(plan.get("tariff_type", "")).strip()
            effective_from = plan.get("effective_from") or today_iso
            daily_supply = plan.get("daily_supply_charge_cents")
            source_url = plan.get("source_url")

            if not retailer or not plan_name or not tariff_type or daily_supply is None or not source_url:
                skipped_missing_fields += 1
                continue

            item = {
                "retailer": retailer,
                "plan_name": plan_name,
                "tariff_type": tariff_type,
                "effective_from": effective_from,
                "effective_to": None,
                "daily_supply_charge_cents": daily_supply,
                "usage_rate_cents_per_kwh": plan.get("usage_rate_cents_per_kwh"),
                "source_url": source_url,
                "customer_type": plan.get("customer_type"),
                "fuel_type": plan.get("fuel_type"),
                "retailer_slug": plan.get("retailer_slug"),
                "plan_id": plan.get("plan_id"),
                "tou_rates": EnergyExpertService.deduplicate_tou_rates(plan.get("tou_rates") or []),
                "feed_in_tariffs": plan.get("feed_in_tariffs") or [],
                "distributors": plan.get("distributors") or [],
                "included_postcodes": plan.get("included_postcodes") or [],
                "state": plan.get("state"),
            }
            dedup_key = self._retail_catalog_dedup_key(item)
            if dedup_key in seen_keys:
                dedup_dropped += 1
                continue
            seen_keys.add(dedup_key)
            plans_out.append(item)

        sources = sorted(
            {
                str(item.get("source_url"))
                for item in plans_out
                if isinstance(item, dict) and item.get("source_url")
            }
        )
        catalog_payload = {
            "metadata": {
                "description": "Retailer plan snapshots from Energy Made Easy CDR API",
                "as_of": today_iso,
                "sources": sources,
            },
            "plans": plans_out,
        }
        stats = {
            "plans_total": len(eme_payload.get("plans", [])) if isinstance(eme_payload.get("plans", []), list) else 0,
            "plans_written": len(plans_out),
            "plans_skipped_missing_fields": skipped_missing_fields,
            "plans_dedup_dropped": dedup_dropped,
        }
        return catalog_payload, stats

    def persist_retail_catalog(self, eme_payload: dict[str, Any], retail_catalog_path: Path = DEFAULT_RETAIL_CATALOG_PATH) -> dict[str, int]:
        catalog_payload, stats = self.build_retail_catalog_payload(eme_payload)
        retail_catalog_path.parent.mkdir(parents=True, exist_ok=True)
        retail_catalog_path.write_text(json.dumps(catalog_payload, indent=2), encoding="utf-8")
        return stats

    @staticmethod
    def extract_retailer_names(dropdown_html: str) -> list[str]:
        names: list[str] = []
        for raw in re.findall(r"<span[^>]*>(.*?)</span>", dropdown_html, flags=re.IGNORECASE | re.DOTALL):
            value = re.sub(r"<[^>]+>", "", unescape(raw)).strip()
            if not value:
                continue
            if value.lower() == _NONE_OPTION:
                continue
            if value not in names:
                names.append(value)
        return names

    @staticmethod
    def slug_candidates_for_name(retailer_name: str) -> list[str]:
        cleaned = unescape(retailer_name).strip()
        candidates: list[str] = []

        if cleaned in RETAILER_SLUG_OVERRIDES:
            candidates.append(RETAILER_SLUG_OVERRIDES[cleaned])

        simplified = re.sub(r"\([^)]*\)", "", cleaned)
        simplified = re.sub(r"[^a-z0-9]+", "-", simplified.lower()).strip("-")
        compact = re.sub(r"[^a-z0-9]+", "", cleaned.lower())

        for candidate in (simplified, compact):
            if candidate and candidate not in candidates:
                candidates.append(candidate)

        return candidates

    @staticmethod
    def next_semiannual_run_utc(reference: datetime | None = None) -> datetime:
        reference = reference or datetime.now(timezone.utc)
        year = reference.year
        candidates = [
            datetime(year, 1, 1, 2, 0, 0, tzinfo=timezone.utc),
            datetime(year, 7, 1, 2, 0, 0, tzinfo=timezone.utc),
            datetime(year + 1, 1, 1, 2, 0, 0, tzinfo=timezone.utc),
        ]
        for candidate in candidates:
            if candidate > reference:
                return candidate
        return datetime(year + 1, 7, 1, 2, 0, 0, tzinfo=timezone.utc)

    @staticmethod
    def _plan_dedup_key(plan: dict[str, Any]) -> tuple:
        plan_id = plan.get("plan_id")
        if plan_id:
            return ("plan_id", str(plan_id))
        distributors = plan.get("distributors") or []
        first_dist = str(distributors[0]).strip().lower() if distributors else ""
        return (
            "fallback",
            str(plan.get("retailer_slug") or plan.get("retailer") or "").strip().lower(),
            str(plan.get("plan_name") or "").strip().lower(),
            str(plan.get("effective_from") or ""),
            str(plan.get("tariff_type") or "").strip().lower(),
            first_dist,
        )

    @staticmethod
    def _retail_catalog_dedup_key(item: dict[str, Any]) -> tuple:
        plan_id = item.get("plan_id")
        if plan_id:
            return ("plan_id", str(plan_id))
        distributors = item.get("distributors") or []
        first_dist = str(distributors[0]).strip().lower() if distributors else ""
        return (
            str(item.get("retailer_slug") or item.get("retailer") or "").strip().lower(),
            str(item.get("plan_name") or "").strip().lower(),
            str(item.get("effective_from") or ""),
            str(item.get("tariff_type") or "").strip().lower(),
            first_dist,
        )
