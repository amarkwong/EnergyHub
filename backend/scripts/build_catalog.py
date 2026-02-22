"""Build pre-computed plan catalog from CDR API.

Replaces the N+1 detail-call pipeline with:
  1. Discover retailers from jxeeno CDR registry
  2. Fetch plan list pages (geography available without detail calls)
  3. Deduplicate by (retailer, name, distributors) — merge postcodes
  4. Fetch details only for unique variants (~3-5K instead of ~15K)
  5. Build postcode index for instant lookups
  6. Write catalog.json

Usage (from backend/):
  python -m scripts.build_catalog
  python -m scripts.build_catalog --retailers agl origin --output /tmp/test.json
  python -m scripts.build_catalog --concurrency 10
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import parse, request as urllib_request

from scripts.fetch_eme_plans import (
    DEFAULT_BASE_URL,
    _derive_state_from_postcode,
    _normalize_plan_summary,
    _request_json,
)
from app.services.energy_expert_service import EnergyExpertService

CDR_REGISTRY_URL = "https://jxeeno.github.io/energy-cdr-prd-endpoints/energy-prd-endpoints.json"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "app" / "data" / "catalog.json"


def _download_registry(registry_url: str, timeout: float) -> list[dict[str, str]]:
    """Fetch retailer list from jxeeno CDR endpoint registry."""
    req = urllib_request.Request(registry_url, headers={"Accept": "application/json"})
    with urllib_request.urlopen(req, timeout=timeout) as resp:
        raw = json.loads(resp.read().decode("utf-8"))

    items = raw.get("data", []) if isinstance(raw, dict) else raw
    entries: list[dict[str, str]] = []
    for item in items:
        industries = item.get("industries") or []
        if not any("energy" in ind.lower() for ind in industries):
            continue
        base_uri = item.get("productReferenceDataBaseUri") or ""
        slug = base_uri.rstrip("/").rsplit("/", 1)[-1] if base_uri else ""
        if not slug:
            continue
        brand_name = item.get("brandName") or slug
        entries.append({"brand_name": brand_name, "slug": slug})
    return entries


def _fetch_list_plans(
    base_url: str, slug: str, page_size: int, timeout: float, fuel_type: str,
) -> list[dict[str, Any]]:
    """Fetch all plan summaries from CDR list endpoint for one retailer."""
    all_plans: list[dict[str, Any]] = []
    page = 1
    while True:
        url = (
            f"{base_url.rstrip('/')}/{slug}/cds-au/v1/energy/plans"
            f"?type=ALL&page={page}&page-size={page_size}"
        )
        result = _request_json(url, preferred_version=1, timeout_seconds=timeout)
        data = result.payload.get("data", {})
        plans = data.get("plans", []) if isinstance(data, dict) else []
        if not plans:
            break
        for plan in plans:
            if not isinstance(plan, dict):
                continue
            if fuel_type != "ALL" and str(plan.get("fuelType", "")).upper() != fuel_type:
                continue
            all_plans.append(plan)
        meta = result.payload.get("meta", {})
        total_pages = meta.get("totalPages") if isinstance(meta, dict) else None
        if isinstance(total_pages, int) and page >= total_pages:
            break
        page += 1
    return all_plans


def _extract_distributors(plan: dict[str, Any]) -> list[str]:
    """Extract distributor names from plan geography."""
    geography = plan.get("geography") or {}
    raw = geography.get("distributors") or []
    names: list[str] = []
    for d in raw:
        if isinstance(d, str):
            name = d
        elif isinstance(d, dict):
            name = d.get("displayName") or d.get("name") or ""
        else:
            continue
        if name and name not in names:
            names.append(name)
    return names


def _extract_postcodes(plan: dict[str, Any]) -> list[str]:
    """Extract postcodes from plan geography."""
    geography = plan.get("geography") or {}
    raw = geography.get("includedPostcodes") or []
    return [str(p) for p in raw if p]


def _group_plans(
    plans: list[dict[str, Any]], retailer_slug: str,
) -> list[dict[str, Any]]:
    """Group plans by (display_name, customer_type, frozenset(distributors)).

    Returns list of group dicts with merged postcodes and all plan IDs.
    """
    groups: dict[tuple, dict[str, Any]] = {}
    for plan in plans:
        display_name = plan.get("displayName") or ""
        customer_type = plan.get("customerType") or ""
        distributors = _extract_distributors(plan)
        postcodes = _extract_postcodes(plan)
        plan_id = plan.get("planId") or ""
        if not plan_id:
            continue

        key = (display_name, customer_type, frozenset(distributors))
        if key not in groups:
            groups[key] = {
                "retailer_slug": retailer_slug,
                "representative_summary": plan,
                "representative_plan_id": plan_id,
                "all_postcodes": set(postcodes),
                "all_plan_ids": [plan_id],
                "distributors": distributors,
                "display_name": display_name,
                "customer_type": customer_type,
            }
        else:
            groups[key]["all_postcodes"].update(postcodes)
            if plan_id not in groups[key]["all_plan_ids"]:
                groups[key]["all_plan_ids"].append(plan_id)

    return list(groups.values())


def _fetch_detail_and_normalize(
    base_url: str,
    group: dict[str, Any],
    retailer_name: str,
    timeout: float,
) -> dict[str, Any] | None:
    """Fetch plan detail for one group and normalize into a catalog entry."""
    slug = group["retailer_slug"]
    plan_id = group["representative_plan_id"]
    summary = group["representative_summary"]

    detail_path = parse.quote(plan_id, safe="")
    detail_url = f"{base_url.rstrip('/')}/{slug}/cds-au/v1/energy/plans/{detail_path}"

    result = _request_json(detail_url, preferred_version=3, timeout_seconds=timeout)
    detail_data = result.payload.get("data", {})
    if not isinstance(detail_data, dict):
        return None

    normalized = _normalize_plan_summary(slug, summary, detail_data, detail_url)

    # Deduplicate TOU rates
    if normalized.get("tou_rates"):
        normalized["tou_rates"] = EnergyExpertService.deduplicate_tou_rates(
            normalized["tou_rates"]
        )

    all_postcodes = sorted(group["all_postcodes"])

    entry: dict[str, Any] = {
        "retailer_slug": slug,
        "retailer": retailer_name,
        "plan_name": normalized.get("plan_name") or group["display_name"],
        "tariff_type": normalized.get("tariff_type", "flat"),
        "customer_type": normalized.get("customer_type") or group["customer_type"],
        "effective_from": normalized.get("effective_from"),
        "daily_supply_charge_cents": normalized.get("daily_supply_charge_cents"),
        "usage_rate_cents_per_kwh": normalized.get("usage_rate_cents_per_kwh"),
        "tou_rates": normalized.get("tou_rates") or [],
        "feed_in_tariffs": normalized.get("feed_in_tariffs") or [],
        "distributors": group["distributors"],
        "state": normalized.get("state"),
        "plan_ids": group["all_plan_ids"],
        "source_url": normalized.get("source_url"),
        "_postcodes": all_postcodes,
    }

    if entry["daily_supply_charge_cents"] is None:
        return None

    return entry


def _build_postcode_index(plans: list[dict[str, Any]]) -> dict[str, list[int]]:
    """Build postcode -> plan indices mapping, removing _postcodes from plans."""
    index: dict[str, list[int]] = {}
    for plan in plans:
        postcodes = plan.pop("_postcodes", [])
        idx = plan["idx"]
        for pc in postcodes:
            index.setdefault(pc, []).append(idx)
    return index


def build_catalog(
    base_url: str,
    retailers: list[dict[str, str]],
    page_size: int,
    concurrency: int,
    timeout: float,
    fuel_type: str,
) -> dict[str, Any]:
    """Build the complete catalog."""
    all_groups: list[dict[str, Any]] = []
    retailer_info: dict[str, dict[str, Any]] = {}
    retailer_name_map: dict[str, str] = {}

    # --- Phase A: Fetch list pages ---
    t0 = time.monotonic()
    for entry in retailers:
        slug = entry["slug"]
        brand_name = entry["brand_name"]

        try:
            list_plans = _fetch_list_plans(base_url, slug, page_size, timeout, fuel_type)
        except Exception as e:
            print(f"  SKIP {slug}: {e}", file=sys.stderr)
            continue

        if not list_plans:
            continue

        groups = _group_plans(list_plans, slug)

        states: set[str] = set()
        for plan in list_plans:
            for pc in _extract_postcodes(plan):
                st = _derive_state_from_postcode(pc)
                if st:
                    states.add(st)

        retailer_info[slug] = {"name": brand_name, "states": sorted(states)}
        retailer_name_map[slug] = brand_name
        all_groups.extend(groups)
        print(f"  {slug}: {len(list_plans)} plans -> {len(groups)} unique variants")

    list_time = time.monotonic() - t0
    print(
        f"\nList phase: {len(all_groups)} unique groups from "
        f"{len(retailer_info)} retailers ({list_time:.1f}s)"
    )

    # --- Phase B: Fetch details with concurrency ---
    print(f"Fetching details (concurrency={concurrency})...")
    t1 = time.monotonic()
    plans_out: list[dict[str, Any]] = []
    errors = 0

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {
            executor.submit(
                _fetch_detail_and_normalize,
                base_url,
                group,
                retailer_name_map.get(group["retailer_slug"], group["retailer_slug"]),
                timeout,
            ): group
            for group in all_groups
        }

        done = 0
        for future in as_completed(futures):
            done += 1
            try:
                plan = future.result()
                if plan:
                    plans_out.append(plan)
            except Exception as e:
                group = futures[future]
                print(
                    f"  ERROR {group['retailer_slug']}/"
                    f"{group['representative_plan_id']}: {e}",
                    file=sys.stderr,
                )
                errors += 1

            if done % 200 == 0:
                print(f"  {done}/{len(all_groups)} details processed...")

    detail_time = time.monotonic() - t1
    print(
        f"Detail phase: {len(plans_out)} plans normalized, "
        f"{errors} errors ({detail_time:.1f}s)"
    )

    # --- Phase C: Sort, assign indices, build postcode index ---
    plans_out.sort(key=lambda p: (p["retailer_slug"], p["plan_name"]))
    for idx, plan in enumerate(plans_out):
        plan["idx"] = idx

    postcode_index = _build_postcode_index(plans_out)

    retailers_list = [
        {"slug": slug, "name": info["name"], "states": info["states"]}
        for slug, info in sorted(retailer_info.items())
    ]

    return {
        "metadata": {
            "version": 1,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "retailer_count": len(retailers_list),
            "plan_count": len(plans_out),
            "postcode_count": len(postcode_index),
        },
        "retailers": retailers_list,
        "plans": plans_out,
        "postcode_index": postcode_index,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build pre-computed plan catalog from CDR API."
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT,
        help="Output catalog.json path",
    )
    parser.add_argument(
        "--retailers", nargs="*",
        help="Specific retailer slugs (default: all from registry)",
    )
    parser.add_argument(
        "--registry-url", default=CDR_REGISTRY_URL,
        help="jxeeno CDR registry URL",
    )
    parser.add_argument(
        "--base-url", default=DEFAULT_BASE_URL, help="CDR API base URL",
    )
    parser.add_argument(
        "--concurrency", type=int, default=5,
        help="Max concurrent detail fetches",
    )
    parser.add_argument(
        "--page-size", type=int, default=1000,
        help="Plans per list page",
    )
    parser.add_argument(
        "--fuel-type", default="ELECTRICITY",
        choices=["ALL", "ELECTRICITY", "GAS"],
    )
    parser.add_argument(
        "--timeout", type=float, default=30.0, help="HTTP timeout seconds",
    )
    args = parser.parse_args()

    if args.retailers:
        retailers = [{"slug": s, "brand_name": s} for s in args.retailers]
        print(f"Using {len(retailers)} specified retailer(s)")
    else:
        print("Discovering retailers from registry...")
        retailers = _download_registry(args.registry_url, args.timeout)
        print(f"Found {len(retailers)} energy retailers")

    catalog = build_catalog(
        base_url=args.base_url,
        retailers=retailers,
        page_size=args.page_size,
        concurrency=args.concurrency,
        timeout=args.timeout,
        fuel_type=args.fuel_type,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(catalog, indent=2), encoding="utf-8")

    size_mb = args.output.stat().st_size / (1024 * 1024)
    meta = catalog["metadata"]
    print(f"\nWrote {meta['plan_count']} plans to {args.output} ({size_mb:.1f} MB)")
    print(f"Retailers: {meta['retailer_count']}")
    print(f"Postcodes indexed: {meta['postcode_count']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
