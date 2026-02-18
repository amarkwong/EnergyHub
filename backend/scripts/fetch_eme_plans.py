"""Fetch Energy Made Easy CDR plans and normalize key pricing fields.

Example:
  python backend/scripts/fetch_eme_plans.py \
    --retailers agl,origin,energyaustralia \
    --max-plans 30 \
    --output backend/app/data/eme_plans_sample.json
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib import error, parse, request


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "app" / "data" / "eme_plans_sample.json"
DEFAULT_BASE_URL = "https://cdr.energymadeeasy.gov.au"


@dataclass
class RequestResult:
    payload: dict[str, Any]
    version_used: int


def _parse_version_hint(detail: str, token: str) -> int | None:
    marker = f"{token}="
    idx = detail.find(marker)
    if idx == -1:
        return None
    idx += len(marker)
    digits: list[str] = []
    while idx < len(detail) and detail[idx].isdigit():
        digits.append(detail[idx])
        idx += 1
    if not digits:
        return None
    return int("".join(digits))


def _http_get_json(url: str, version: int, timeout_seconds: float) -> tuple[int, dict[str, Any]]:
    req = request.Request(url, headers={"x-v": str(version), "Accept": "application/json"})
    try:
        with request.urlopen(req, timeout=timeout_seconds) as resp:
            body = resp.read().decode("utf-8")
            return int(resp.status), json.loads(body)
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8") if exc.fp else "{}"
        try:
            payload = json.loads(body)
        except Exception:
            payload = {"errors": [{"code": f"HTTP_{exc.code}", "detail": body}]}
        return int(exc.code), payload


def _request_json(url: str, preferred_version: int, timeout_seconds: float) -> RequestResult:
    version = preferred_version
    for _ in range(3):
        status_code, payload = _http_get_json(url, version=version, timeout_seconds=timeout_seconds)
        if status_code < 400:
            return RequestResult(payload=payload, version_used=version)

        errors = payload.get("errors") if isinstance(payload, dict) else None
        if not isinstance(errors, list) or not errors or not isinstance(errors[0], dict):
            raise RuntimeError(f"Request failed: status={status_code}, url={url}, payload={payload}")

        code = str(errors[0].get("code", ""))
        detail = str(errors[0].get("detail", ""))
        if "UnsupportedVersion" not in code:
            raise RuntimeError(f"Request failed: status={status_code}, url={url}, payload={payload}")

        min_supported = _parse_version_hint(detail, "min")
        max_supported = _parse_version_hint(detail, "max")
        next_version = min_supported if min_supported is not None else max_supported
        if next_version is None or next_version == version:
            raise RuntimeError(f"Could not negotiate version: url={url}, detail={detail}")
        version = next_version

    raise RuntimeError(f"Failed to negotiate CDR version for URL: {url}")


def _derive_state_from_postcode(postcode: str) -> str | None:
    """Map Australian postcode prefix to state abbreviation."""
    if not postcode or not postcode[0].isdigit():
        return None
    first = int(postcode[0])
    mapping = {
        2: "NSW", 3: "VIC", 4: "QLD", 5: "SA",
        6: "WA", 7: "TAS", 0: "NT",
    }
    # ACT postcodes: 2600-2618, 2900-2920
    if postcode.startswith(("26", "29")) and first == 2:
        try:
            num = int(postcode)
            if 2600 <= num <= 2618 or 2900 <= num <= 2920:
                return "ACT"
        except ValueError:
            pass
    return mapping.get(first)


def _to_cents(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(Decimal(str(value)) * Decimal("100"))
    except (InvalidOperation, ValueError):
        return None


def _pick_first_unit_price_cents(contract: dict[str, Any]) -> float | None:
    tariff_periods = contract.get("tariffPeriod")
    if not isinstance(tariff_periods, list):
        return None

    for period in tariff_periods:
        if not isinstance(period, dict):
            continue

        single_rate = period.get("singleRate")
        if isinstance(single_rate, dict):
            rates = single_rate.get("rates")
            if isinstance(rates, list):
                for rate in rates:
                    if isinstance(rate, dict) and "unitPrice" in rate:
                        cents = _to_cents(rate.get("unitPrice"))
                        if cents is not None:
                            return cents

        tou_rates = period.get("timeOfUseRates")
        if isinstance(tou_rates, list):
            for tou_rate in tou_rates:
                if not isinstance(tou_rate, dict):
                    continue
                # CDR spec: unitPrice is nested inside rates[]
                nested_rates = tou_rate.get("rates")
                if isinstance(nested_rates, list):
                    for rate in nested_rates:
                        if isinstance(rate, dict) and "unitPrice" in rate:
                            cents = _to_cents(rate.get("unitPrice"))
                            if cents is not None:
                                return cents
                # Fallback: unitPrice directly on tou_rate (older API versions)
                if "unitPrice" in tou_rate:
                    cents = _to_cents(tou_rate.get("unitPrice"))
                    if cents is not None:
                        return cents

    return None


# CDR day names → Python weekday ints (Monday=0)
# API returns both full names and 3-letter abbreviations
_CDR_DAY_MAP: dict[str, int] = {
    "MONDAY": 0, "MON": 0,
    "TUESDAY": 1, "TUE": 1,
    "WEDNESDAY": 2, "WED": 2,
    "THURSDAY": 3, "THU": 3,
    "FRIDAY": 4, "FRI": 4,
    "SATURDAY": 5, "SAT": 5,
    "SUNDAY": 6, "SUN": 6,
    "PUBLIC_HOLIDAYS": -1,
}


def _extract_tou_rates(contract: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract per-period TOU rates from CDR contract tariffPeriod.

    Each CDR timeOfUseRate can have multiple timeOfUse windows (e.g. peak
    covers 06:00-09:59 and 15:00-20:59). We emit one entry per window so
    the downstream TOU period model can represent them individually.
    """
    tariff_periods = contract.get("tariffPeriod")
    if not isinstance(tariff_periods, list):
        return []

    results: list[dict[str, Any]] = []
    for period in tariff_periods:
        if not isinstance(period, dict):
            continue
        tou_rates = period.get("timeOfUseRates")
        if not isinstance(tou_rates, list):
            continue
        for tou_rate in tou_rates:
            if not isinstance(tou_rate, dict):
                continue

            # Extract rate (cents) from nested rates[]
            rate_cents: float | None = None
            nested_rates = tou_rate.get("rates")
            if isinstance(nested_rates, list):
                for rate in nested_rates:
                    if isinstance(rate, dict) and "unitPrice" in rate:
                        rate_cents = _to_cents(rate.get("unitPrice"))
                        if rate_cents is not None:
                            break
            if rate_cents is None and "unitPrice" in tou_rate:
                rate_cents = _to_cents(tou_rate.get("unitPrice"))

            # Normalize type to our naming convention
            tou_type = (tou_rate.get("type") or "").strip().upper()
            name = tou_type.lower().replace(" ", "_")
            if name in ("offpeak",):
                name = "off_peak"

            # Emit one entry per timeOfUse window (e.g. peak may cover two disjoint windows)
            time_of_use = tou_rate.get("timeOfUse")
            if isinstance(time_of_use, list) and time_of_use:
                for window in time_of_use:
                    if not isinstance(window, dict):
                        continue
                    start_time = str(window.get("startTime") or "")[:5] or None
                    end_time = str(window.get("endTime") or "")[:5] or None
                    days: list[int] = []
                    for day_name in (window.get("days") or []):
                        day_int = _CDR_DAY_MAP.get(str(day_name).upper(), -1)
                        if day_int >= 0 and day_int not in days:
                            days.append(day_int)
                    results.append({
                        "name": name or "unknown",
                        "rate_cents_per_kwh": rate_cents,
                        "start_time": start_time,
                        "end_time": end_time,
                        "days": sorted(days) if days else None,
                    })
            else:
                # No time windows — emit rate without time info
                results.append({
                    "name": name or "unknown",
                    "rate_cents_per_kwh": rate_cents,
                    "start_time": None,
                    "end_time": None,
                    "days": None,
                })

    # Deduplicate: CDR contracts have multiple tariffPeriod blocks (general
    # usage, controlled load, demand) that repeat the same TOU windows.
    seen: set[tuple] = set()
    deduped: list[dict[str, Any]] = []
    for entry in results:
        key = (
            entry.get("name"),
            entry.get("rate_cents_per_kwh"),
            entry.get("start_time"),
            entry.get("end_time"),
            tuple(entry["days"]) if entry.get("days") else None,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return deduped


def _extract_daily_supply_cents(contract: dict[str, Any]) -> float | None:
    tariff_periods = contract.get("tariffPeriod")
    if not isinstance(tariff_periods, list):
        return None

    for period in tariff_periods:
        if not isinstance(period, dict):
            continue
        cents = _to_cents(period.get("dailySupplyCharge"))
        if cents is not None:
            return cents

    return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pick_field(node: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in node and node.get(name) is not None:
            return node.get(name)
    return None


def _walk_unit_price_nodes(node: Any, collector: list[dict[str, Any]], context: dict[str, Any]) -> None:
    if isinstance(node, list):
        for item in node:
            _walk_unit_price_nodes(item, collector, context)
        return

    if not isinstance(node, dict):
        return

    local_context = dict(context)
    for field in ("name", "displayName", "description", "type", "rateName"):
        value = node.get(field)
        if isinstance(value, str) and value.strip():
            local_context[field] = value.strip()

    if "unitPrice" in node:
        unit_price_cents = _to_cents(node.get("unitPrice"))
        if unit_price_cents is not None:
            entry = {
                "unit_price_cents_per_kwh": unit_price_cents,
                "name": local_context.get("name") or local_context.get("displayName") or local_context.get("description"),
                "type": local_context.get("type"),
                "period_name": context.get("period_name"),
                "time_from": _pick_field(node, "from", "startTime"),
                "time_to": _pick_field(node, "to", "endTime"),
                "tier_min_kwh": _to_float(_pick_field(node, "min", "tierMin", "start")),
                "tier_max_kwh": _to_float(_pick_field(node, "max", "tierMax", "end")),
            }
            collector.append(entry)

    for value in node.values():
        _walk_unit_price_nodes(value, collector, local_context)


def _extract_feed_in_tariffs(contract: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    periods = contract.get("tariffPeriod")
    if isinstance(periods, list):
        for idx, period in enumerate(periods):
            if not isinstance(period, dict):
                continue
            period_name = period.get("displayName") or period.get("name") or f"tariff_period_{idx+1}"
            for key in ("feedInTariff", "solarFeedInTariff", "feedInRates", "solarFeedInRates"):
                section = period.get(key)
                if section is None:
                    continue
                _walk_unit_price_nodes(section, candidates, {"period_name": str(period_name), "section": key})

    for key in ("feedInTariff", "solarFeedInTariff", "feedInRates", "solarFeedInRates"):
        section = contract.get(key)
        if section is None:
            continue
        _walk_unit_price_nodes(section, candidates, {"period_name": None, "section": key})

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for row in candidates:
        key = (
            row.get("unit_price_cents_per_kwh"),
            row.get("period_name"),
            row.get("time_from"),
            row.get("time_to"),
            row.get("tier_min_kwh"),
            row.get("tier_max_kwh"),
            row.get("name"),
            row.get("type"),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return _infer_feed_in_tiers(deduped)


def _infer_feed_in_tiers(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Infer tier bounds when API omits min/max but labels imply tiers."""
    if len(rows) < 2:
        return rows

    inferred = [dict(r) for r in rows]
    first_kwh = None

    for row in inferred:
        if row.get("tier_min_kwh") is not None or row.get("tier_max_kwh") is not None:
            continue
        name = str(row.get("name") or "").lower()
        match = re.search(r"first\s+(\d+(?:\.\d+)?)\s*kwh", name)
        if match:
            first_kwh = float(match.group(1))
            break

    if first_kwh is None:
        return inferred

    # If all tiers have missing bounds, infer by order:
    # first row = 0..N, subsequent rows = N..None
    all_missing = all(r.get("tier_min_kwh") is None and r.get("tier_max_kwh") is None for r in inferred)
    if all_missing:
        inferred[0]["tier_min_kwh"] = 0.0
        inferred[0]["tier_max_kwh"] = first_kwh
        inferred[0]["tier_inferred"] = True
        for idx in range(1, len(inferred)):
            inferred[idx]["tier_min_kwh"] = first_kwh
            inferred[idx]["tier_max_kwh"] = None
            inferred[idx]["tier_inferred"] = True

    return inferred


def _normalize_plan_summary(
    retailer_slug: str,
    plan_summary: dict[str, Any],
    plan_detail: dict[str, Any],
    detail_url: str,
) -> dict[str, Any]:
    contract = plan_detail.get("electricityContract") or plan_detail.get("gasContract") or {}

    effective_from = plan_summary.get("effectiveFrom") or plan_detail.get("effectiveFrom")
    effective_date = None
    if isinstance(effective_from, str) and effective_from:
        try:
            effective_date = datetime.fromisoformat(effective_from.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            effective_date = effective_from

    pricing_model = contract.get("pricingModel")
    tariff_type = "flat"
    if isinstance(pricing_model, str):
        normalized = pricing_model.strip().upper()
        if "TOU" in normalized or "TIME" in normalized:
            tariff_type = "tou"
        elif "DEMAND" in normalized:
            tariff_type = "demand"
        elif "SINGLE" in normalized:
            tariff_type = "flat"

    # Extract geography from plan summary (CDR list endpoint provides this)
    geography = plan_summary.get("geography") or {}
    distributors: list[str] = []
    if isinstance(geography.get("distributors"), list):
        for d in geography["distributors"]:
            name = d if isinstance(d, str) else (d.get("displayName") or d.get("name") or "") if isinstance(d, dict) else ""
            if name and name not in distributors:
                distributors.append(name)
    included_postcodes: list[str] = []
    if isinstance(geography.get("includedPostcodes"), list):
        included_postcodes = [str(p) for p in geography["includedPostcodes"] if p]

    # Derive state from first postcode if available
    state: str | None = None
    if included_postcodes:
        state = _derive_state_from_postcode(included_postcodes[0])

    return {
        "retailer": plan_summary.get("brandName") or plan_detail.get("brandName") or retailer_slug,
        "retailer_slug": retailer_slug,
        "plan_id": plan_summary.get("planId") or plan_detail.get("planId"),
        "plan_name": plan_summary.get("displayName") or plan_detail.get("displayName"),
        "fuel_type": plan_summary.get("fuelType") or plan_detail.get("fuelType"),
        "customer_type": plan_summary.get("customerType") or plan_detail.get("customerType"),
        "effective_from": effective_date,
        "daily_supply_charge_cents": _extract_daily_supply_cents(contract),
        "usage_rate_cents_per_kwh": _pick_first_unit_price_cents(contract),
        "tou_rates": _extract_tou_rates(contract),
        "feed_in_tariffs": _extract_feed_in_tariffs(contract),
        "tariff_type": tariff_type,
        "source_url": detail_url,
        "distributors": distributors,
        "included_postcodes": included_postcodes,
        "state": state,
    }


def fetch_retailer_plans(
    base_url: str,
    retailer_slug: str,
    page_size: int,
    max_plans: int,
    fuel_type: str,
    timeout_seconds: float,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    normalized: list[dict[str, Any]] = []
    pages_fetched = 0
    detail_calls = 0

    page = 1
    while True:
        list_url = (
            f"{base_url.rstrip('/')}/{retailer_slug}/cds-au/v1/energy/plans"
            f"?type=ALL&page={page}&page-size={page_size}"
        )
        list_result = _request_json(list_url, preferred_version=1, timeout_seconds=timeout_seconds)
        pages_fetched += 1

        data = list_result.payload.get("data", {})
        plans = data.get("plans", []) if isinstance(data, dict) else []
        if not isinstance(plans, list) or not plans:
            break

        for plan in plans:
            if not isinstance(plan, dict):
                continue
            if fuel_type != "ALL" and str(plan.get("fuelType", "")).upper() != fuel_type:
                continue

            plan_id = plan.get("planId")
            if not isinstance(plan_id, str) or not plan_id:
                continue

            detail_path = parse.quote(plan_id, safe="")
            detail_url = f"{base_url.rstrip('/')}/{retailer_slug}/cds-au/v1/energy/plans/{detail_path}"
            detail_result = _request_json(detail_url, preferred_version=3, timeout_seconds=timeout_seconds)
            detail_calls += 1

            detail_data = detail_result.payload.get("data", {}) if isinstance(detail_result.payload, dict) else {}
            if not isinstance(detail_data, dict):
                continue

            normalized.append(_normalize_plan_summary(retailer_slug, plan, detail_data, detail_url))
            if max_plans > 0 and len(normalized) >= max_plans:
                return normalized, {"pages_fetched": pages_fetched, "detail_calls": detail_calls}

        meta = list_result.payload.get("meta", {})
        total_pages = meta.get("totalPages") if isinstance(meta, dict) else None
        if isinstance(total_pages, int) and page >= total_pages:
            break
        page += 1

    return normalized, {"pages_fetched": pages_fetched, "detail_calls": detail_calls}


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch plans from Energy Made Easy CDR API.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="CDR base URL.")
    parser.add_argument("--retailers", default="agl", help="Comma-separated retailer base URI slugs.")
    parser.add_argument("--page-size", type=int, default=10, help="List API page size.")
    parser.add_argument("--max-plans", type=int, default=20, help="Maximum normalized plans per retailer.")
    parser.add_argument("--fuel-type", choices=["ALL", "ELECTRICITY", "GAS"], default="ELECTRICITY")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    retailers = [item.strip() for item in args.retailers.split(",") if item.strip()]
    if not retailers:
        raise SystemExit("No retailers provided")

    output_payload: dict[str, Any] = {
        "metadata": {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "source": "AER CDR Energy Product Reference Data API",
            "base_url": args.base_url,
            "retailers": retailers,
            "fuel_type": args.fuel_type,
        },
        "plans": [],
        "stats": {},
    }

    for retailer in retailers:
        plans, stats = fetch_retailer_plans(
            base_url=args.base_url,
            retailer_slug=retailer,
            page_size=args.page_size,
            max_plans=args.max_plans,
            fuel_type=args.fuel_type,
            timeout_seconds=args.timeout_seconds,
        )
        output_payload["plans"].extend(plans)
        output_payload["stats"][retailer] = {
            **stats,
            "plans_normalized": len(plans),
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output_payload, indent=2), encoding="utf-8")

    print(f"Wrote {len(output_payload['plans'])} plans to {args.output}")
    print(json.dumps(output_payload["stats"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
