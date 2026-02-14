"""Validate energy plan and tariff data sources and structure."""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.tariff import NetworkProvider

NETWORK_PATH = ROOT / "app" / "data" / "network_tariffs.json"
RETAIL_PATH = ROOT / "app" / "data" / "retail_plans.json"


MAJOR_RETAILERS = {"AGL", "Origin Energy", "EnergyAustralia"}


def _is_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_catalog_files() -> tuple[list[str], dict]:
    errors: list[str] = []
    summary: dict = {}

    network = _load_json(NETWORK_PATH)
    retail = _load_json(RETAIL_PATH)

    network_sources = set(network.get("metadata", {}).get("sources", []))
    retail_sources = set(retail.get("metadata", {}).get("sources", []))

    if not network_sources:
        errors.append("network_tariffs.json metadata.sources is empty")
    if not retail_sources:
        errors.append("retail_plans.json metadata.sources is empty")

    for src in [*network_sources, *retail_sources]:
        if not _is_url(src):
            errors.append(f"invalid source URL in metadata.sources: {src}")

    tariffs = network.get("tariffs", [])
    if not tariffs:
        errors.append("network_tariffs.json has no tariffs")

    providers_present = set()
    by_year = defaultdict(int)
    for t in tariffs:
        for field in ["tariff_code", "tariff_name", "network_provider", "tariff_type", "effective_from", "source_url"]:
            if field not in t:
                errors.append(f"network tariff missing field {field}: {t}")
        if "source_url" in t and not _is_url(t["source_url"]):
            errors.append(f"invalid tariff source_url: {t.get('source_url')}")
        try:
            year = date.fromisoformat(t["effective_from"]).year
            by_year[year] += 1
        except Exception:
            errors.append(f"invalid tariff effective_from: {t.get('effective_from')}")

        providers_present.add(t.get("network_provider"))
        for period in t.get("time_periods", []):
            if "name" not in period or "rate_cents_per_kwh" not in period:
                errors.append(f"invalid tariff time_period shape: {period}")

    expected_providers = {p.value for p in NetworkProvider}
    missing_providers = sorted(expected_providers - providers_present)
    if missing_providers:
        errors.append(f"missing network provider tariffs: {missing_providers}")

    plans = retail.get("plans", [])
    if not plans:
        errors.append("retail_plans.json has no plans")

    retailers_present = set()
    plan_years = defaultdict(int)
    for p in plans:
        for field in ["retailer", "plan_name", "tariff_type", "effective_from", "source_url"]:
            if field not in p:
                errors.append(f"retail plan missing field {field}: {p}")
        if "source_url" in p and not _is_url(p["source_url"]):
            errors.append(f"invalid retail plan source_url: {p.get('source_url')}")
        try:
            year = date.fromisoformat(p["effective_from"]).year
            plan_years[year] += 1
        except Exception:
            errors.append(f"invalid plan effective_from: {p.get('effective_from')}")
        retailers_present.add(p.get("retailer"))

    missing_retailers = sorted(MAJOR_RETAILERS - retailers_present)
    if missing_retailers:
        errors.append(f"missing major retailers in catalog: {missing_retailers}")

    summary["network_tariffs_count"] = len(tariffs)
    summary["network_tariffs_by_year"] = dict(sorted(by_year.items(), reverse=True))
    summary["providers_count"] = len(providers_present)
    summary["providers_expected"] = len(expected_providers)
    summary["retail_plans_count"] = len(plans)
    summary["retail_plans_by_year"] = dict(sorted(plan_years.items(), reverse=True))
    summary["retailers_count"] = len(retailers_present)
    return errors, summary


def validate_api_smoke() -> tuple[list[str], dict]:
    errors: list[str] = []
    summary: dict = {}
    client = TestClient(app)

    refresh = client.post("/api/energy-plans/refresh")
    if refresh.status_code != 200:
        errors.append(f"energy plan refresh failed: {refresh.status_code} {refresh.text}")
        return errors, summary

    retailers = client.get("/api/energy-plans/retailers")
    if retailers.status_code != 200:
        errors.append(f"retailers endpoint failed: {retailers.status_code}")
    retailers_payload = retailers.json() if retailers.status_code == 200 else []
    summary["api_retailers_count"] = len(retailers_payload)

    plans = client.get("/api/energy-plans/plans")
    if plans.status_code != 200:
        errors.append(f"plans endpoint failed: {plans.status_code}")
    plans_payload = plans.json() if plans.status_code == 200 else []
    summary["api_plans_count"] = len(plans_payload)

    history = client.get("/api/energy-plans/history")
    if history.status_code != 200:
        errors.append(f"plan history endpoint failed: {history.status_code}")
    history_payload = history.json() if history.status_code == 200 else []
    summary["api_plan_history_years"] = [h.get("year") for h in history_payload]

    providers_resp = client.get("/api/tariffs/network-providers")
    if providers_resp.status_code != 200:
        errors.append(f"network providers endpoint failed: {providers_resp.status_code}")
        return errors, summary

    provider_codes = [p["code"] for p in providers_resp.json()]
    missing_provider_data = []
    for code in provider_codes:
        tariffs = client.get(f"/api/tariffs/network/{code}")
        if tariffs.status_code != 200:
            errors.append(f"network tariff endpoint failed for {code}: {tariffs.status_code}")
            continue
        if len(tariffs.json()) == 0:
            missing_provider_data.append(code)

        hist = client.get(f"/api/tariffs/network/{code}/history")
        if hist.status_code != 200:
            errors.append(f"network history endpoint failed for {code}: {hist.status_code}")

    if missing_provider_data:
        errors.append(f"no tariff rows for providers: {missing_provider_data}")

    summary["api_network_providers_count"] = len(provider_codes)
    summary["api_missing_provider_tariffs"] = missing_provider_data
    return errors, summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate pricing catalogs and APIs.")
    parser.add_argument("--api-smoke", action="store_true", help="Run API-level smoke validation in addition to file checks.")
    args = parser.parse_args()

    file_errors, file_summary = validate_catalog_files()
    print("Catalog validation summary:")
    print(json.dumps(file_summary, indent=2))

    errors = list(file_errors)

    if args.api_smoke:
        api_errors, api_summary = validate_api_smoke()
        print("API validation summary:")
        print(json.dumps(api_summary, indent=2))
        errors.extend(api_errors)

    if errors:
        print("Validation errors:")
        for err in errors:
            print(f"- {err}")
        return 1

    print("Validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
