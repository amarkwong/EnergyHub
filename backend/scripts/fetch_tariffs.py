"""Refresh network tariff catalog from public source pages.

This script updates backend/app/data/network_tariffs.json by:
1) Seeding baseline tariffs for all supported network providers.
2) Fetching configured source URLs.
3) Extracting candidate rates using resilient regex rules.
4) Falling back to seeded/existing values when extraction is unavailable.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import date
from html import unescape
from pathlib import Path
from typing import Optional

import httpx


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "app" / "data" / "network_tariffs.json"


BASELINE_TARIFFS = [
    {
        "tariff_code": "EA010",
        "tariff_name": "Residential Time of Use",
        "network_provider": "ausgrid",
        "tariff_type": "tou",
        "effective_from": "2024-07-01",
        "daily_supply_charge_cents": 98.37,
        "time_periods": [
            {"name": "peak", "rate_cents_per_kwh": 35.64},
            {"name": "shoulder", "rate_cents_per_kwh": 12.87},
            {"name": "off_peak", "rate_cents_per_kwh": 8.14},
        ],
        "source_url": "https://www.aer.gov.au",
    },
    {
        "tariff_code": "EA025",
        "tariff_name": "Residential Flat Rate",
        "network_provider": "ausgrid",
        "tariff_type": "flat",
        "effective_from": "2024-07-01",
        "daily_supply_charge_cents": 98.37,
        "usage_rate_cents_per_kwh": 18.45,
        "source_url": "https://www.aer.gov.au",
    },
    {
        "tariff_code": "N70",
        "tariff_name": "Residential Time of Use",
        "network_provider": "endeavour_energy",
        "tariff_type": "tou",
        "effective_from": "2024-07-01",
        "daily_supply_charge_cents": 89.50,
        "time_periods": [
            {"name": "peak", "rate_cents_per_kwh": 29.82},
            {"name": "shoulder", "rate_cents_per_kwh": 11.43},
            {"name": "off_peak", "rate_cents_per_kwh": 7.89},
        ],
        "source_url": "https://www.aer.gov.au",
    },
    {
        "tariff_code": "BLNN2AU",
        "tariff_name": "Residential Single Rate",
        "network_provider": "essential_energy",
        "tariff_type": "flat",
        "effective_from": "2024-07-01",
        "daily_supply_charge_cents": 115.20,
        "usage_rate_cents_per_kwh": 14.85,
        "source_url": "https://www.aer.gov.au",
    },
    {
        "tariff_code": "NAST11",
        "tariff_name": "Small Residential TOU Weekday",
        "network_provider": "ausnet_services",
        "tariff_type": "tou",
        "effective_from": "2024-01-01",
        "daily_supply_charge_cents": 41.60,
        "time_periods": [
            {"name": "peak", "rate_cents_per_kwh": 18.14},
            {"name": "off_peak", "rate_cents_per_kwh": 6.83},
        ],
        "source_url": "https://www.aer.gov.au",
    },
    {
        "tariff_code": "C1R",
        "tariff_name": "Residential Single Rate",
        "network_provider": "citipower",
        "tariff_type": "flat",
        "effective_from": "2024-01-01",
        "daily_supply_charge_cents": 31.90,
        "usage_rate_cents_per_kwh": 8.75,
        "source_url": "https://www.aer.gov.au",
    },
    {
        "tariff_code": "D1",
        "tariff_name": "Residential Single Rate",
        "network_provider": "powercor",
        "tariff_type": "flat",
        "effective_from": "2024-01-01",
        "daily_supply_charge_cents": 55.20,
        "usage_rate_cents_per_kwh": 9.85,
        "source_url": "https://www.aer.gov.au",
    },
    {
        "tariff_code": "A100",
        "tariff_name": "Residential Anytime",
        "network_provider": "jemena",
        "tariff_type": "flat",
        "effective_from": "2024-01-01",
        "daily_supply_charge_cents": 36.70,
        "usage_rate_cents_per_kwh": 8.25,
        "source_url": "https://www.aer.gov.au",
    },
    {
        "tariff_code": "LVS1R",
        "tariff_name": "Residential Single Rate",
        "network_provider": "united_energy",
        "tariff_type": "flat",
        "effective_from": "2024-01-01",
        "daily_supply_charge_cents": 34.50,
        "usage_rate_cents_per_kwh": 8.45,
        "source_url": "https://www.aer.gov.au",
    },
    {
        "tariff_code": "8400",
        "tariff_name": "Residential Flat",
        "network_provider": "energex",
        "tariff_type": "flat",
        "effective_from": "2024-07-01",
        "daily_supply_charge_cents": 55.80,
        "usage_rate_cents_per_kwh": 11.23,
        "source_url": "https://www.energex.com.au/manage-your-energy/save-money-and-electricity/tariffs/residential-tariffs",
    },
    {
        "tariff_code": "11",
        "tariff_name": "Residential Flat Rate",
        "network_provider": "ergon_energy",
        "tariff_type": "flat",
        "effective_from": "2025-07-01",
        "daily_supply_charge_cents": 168.842,
        "usage_rate_cents_per_kwh": 32.973,
        "source_url": "https://www.ergon.com.au/retail/residential/tariffs-and-prices/compare-residential-tariffs",
    },
    {
        "tariff_code": "12D",
        "tariff_name": "Time of Use",
        "network_provider": "ergon_energy",
        "tariff_type": "tou",
        "effective_from": "2025-07-01",
        "daily_supply_charge_cents": 148.834,
        "time_periods": [
            {"name": "off_peak", "start_time": "11:00", "end_time": "16:00", "days": [0, 1, 2, 3, 4, 5, 6], "rate_cents_per_kwh": 22.68},
            {"name": "night", "start_time": "21:00", "end_time": "11:00", "days": [0, 1, 2, 3, 4, 5, 6], "rate_cents_per_kwh": 28.035},
            {"name": "peak", "start_time": "16:00", "end_time": "21:00", "days": [0, 1, 2, 3, 4, 5, 6], "rate_cents_per_kwh": 45.712},
        ],
        "source_url": "https://www.ergon.com.au/retail/residential/tariffs-and-prices/compare-residential-tariffs",
    },
    {
        "tariff_code": "12E",
        "tariff_name": "Solar Soaker (Time of Use)",
        "network_provider": "ergon_energy",
        "tariff_type": "tou",
        "effective_from": "2025-07-01",
        "daily_supply_charge_cents": 148.834,
        "time_periods": [
            {"name": "off_peak", "start_time": "11:00", "end_time": "16:00", "days": [0, 1, 2, 3, 4, 5, 6], "rate_cents_per_kwh": 7.724},
            {"name": "night", "start_time": "21:00", "end_time": "11:00", "days": [0, 1, 2, 3, 4, 5, 6], "rate_cents_per_kwh": 26.375},
            {"name": "peak", "start_time": "16:00", "end_time": "21:00", "days": [0, 1, 2, 3, 4, 5, 6], "rate_cents_per_kwh": 57.363},
        ],
        "source_url": "https://www.ergon.com.au/retail/residential/tariffs-and-prices/compare-residential-tariffs",
    },
    {
        "tariff_code": "14C",
        "tariff_name": "Time of Use Demand",
        "network_provider": "ergon_energy",
        "tariff_type": "demand",
        "effective_from": "2025-07-01",
        "daily_supply_charge_cents": 126.666,
        "demand_rate_cents_per_kw": 853.49,
        "time_periods": [
            {"name": "off_peak", "start_time": "11:00", "end_time": "16:00", "days": [0, 1, 2, 3, 4, 5, 6], "rate_cents_per_kwh": 22.68},
            {"name": "night", "start_time": "21:00", "end_time": "11:00", "days": [0, 1, 2, 3, 4, 5, 6], "rate_cents_per_kwh": 28.035},
            {"name": "peak", "start_time": "16:00", "end_time": "21:00", "days": [0, 1, 2, 3, 4, 5, 6], "rate_cents_per_kwh": 24.984},
        ],
        "source_url": "https://www.ergon.com.au/retail/residential/tariffs-and-prices/compare-residential-tariffs",
    },
    {
        "tariff_code": "RES-TOU",
        "tariff_name": "Residential Time of Use",
        "network_provider": "evoenergy",
        "tariff_type": "tou",
        "effective_from": "2024-07-01",
        "daily_supply_charge_cents": 52.30,
        "time_periods": [
            {"name": "peak", "rate_cents_per_kwh": 24.50},
            {"name": "off_peak", "rate_cents_per_kwh": 8.90},
        ],
        "source_url": "https://evoenergy.com.au/Your-Energy/Pricing-and-tariffs/Electricity-network-pricing",
    },
    {
        "tariff_code": "TAS31",
        "tariff_name": "Residential Light and Power",
        "network_provider": "tasnetworks",
        "tariff_type": "flat",
        "effective_from": "2024-07-01",
        "daily_supply_charge_cents": 42.50,
        "usage_rate_cents_per_kwh": 12.80,
        "source_url": "https://www.aer.gov.au",
    },
]


def _to_float(value: str) -> Optional[float]:
    normalized = value.replace(",", "").strip()
    try:
        return float(normalized)
    except ValueError:
        return None


def _clean_html_to_text(html: str) -> str:
    without_scripts = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    without_styles = re.sub(r"(?is)<style.*?>.*?</style>", " ", without_scripts)
    text = re.sub(r"(?s)<[^>]+>", " ", without_styles)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_cents(text: str, patterns: list[str]) -> Optional[float]:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue

        raw = _to_float(match.group("value"))
        if raw is None:
            continue

        snippet = match.group(0).lower()
        if "$" in snippet:
            return round(raw * 100, 4)
        return round(raw, 4)
    return None


@dataclass(frozen=True)
class TariffExtractionSpec:
    network_provider: str
    tariff_code: str
    source_url: str
    daily_patterns: list[str]
    usage_patterns: list[str]
    peak_patterns: list[str]
    shoulder_patterns: list[str]
    off_peak_patterns: list[str]


EXTRACTION_SPECS = [
    TariffExtractionSpec(
        network_provider="ausgrid",
        tariff_code="EA010",
        source_url="https://www.aer.gov.au",
        daily_patterns=[
            r"(?:daily|service|supply)\s+(?:charge|price)[^$c]{0,80}(?P<value>\d+(?:\.\d+)?)\s*(?:c|cents?)",
            r"(?:daily|service|supply)\s+(?:charge|price)[^$]{0,80}\$(?P<value>\d+(?:\.\d+)?)",
        ],
        usage_patterns=[],
        peak_patterns=[
            r"(?:peak)[^$c]{0,80}(?P<value>\d+(?:\.\d+)?)\s*(?:c|cents?)\s*/\s*kwh",
            r"(?:peak)[^$]{0,80}\$(?P<value>\d+(?:\.\d+)?)\s*/\s*kwh",
        ],
        shoulder_patterns=[
            r"(?:shoulder)[^$c]{0,80}(?P<value>\d+(?:\.\d+)?)\s*(?:c|cents?)\s*/\s*kwh",
            r"(?:shoulder)[^$]{0,80}\$(?P<value>\d+(?:\.\d+)?)\s*/\s*kwh",
        ],
        off_peak_patterns=[
            r"(?:off[\s-]*peak)[^$c]{0,80}(?P<value>\d+(?:\.\d+)?)\s*(?:c|cents?)\s*/\s*kwh",
            r"(?:off[\s-]*peak)[^$]{0,80}\$(?P<value>\d+(?:\.\d+)?)\s*/\s*kwh",
        ],
    ),
    TariffExtractionSpec(
        network_provider="ausgrid",
        tariff_code="EA025",
        source_url="https://www.aer.gov.au",
        daily_patterns=[
            r"(?:daily|service|supply)\s+(?:charge|price)[^$c]{0,80}(?P<value>\d+(?:\.\d+)?)\s*(?:c|cents?)",
            r"(?:daily|service|supply)\s+(?:charge|price)[^$]{0,80}\$(?P<value>\d+(?:\.\d+)?)",
        ],
        usage_patterns=[
            r"(?:flat|single)\s*(?:rate|usage|energy)[^$c]{0,80}(?P<value>\d+(?:\.\d+)?)\s*(?:c|cents?)\s*/\s*kwh",
            r"(?:flat|single)\s*(?:rate|usage|energy)[^$]{0,80}\$(?P<value>\d+(?:\.\d+)?)\s*/\s*kwh",
        ],
        peak_patterns=[],
        shoulder_patterns=[],
        off_peak_patterns=[],
    ),
    TariffExtractionSpec(
        network_provider="energex",
        tariff_code="8400",
        source_url="https://www.energex.com.au/manage-your-energy/save-money-and-electricity/tariffs/residential-tariffs",
        daily_patterns=[
            r"(?:daily|service|supply)\s+(?:charge|price)[^$c]{0,100}(?P<value>\d+(?:\.\d+)?)\s*(?:c|cents?)",
            r"(?:daily|service|supply)\s+(?:charge|price)[^$]{0,100}\$(?P<value>\d+(?:\.\d+)?)",
        ],
        usage_patterns=[
            r"(?:usage|energy|flat|single)\s*(?:rate|charge|price)[^$c]{0,100}(?P<value>\d+(?:\.\d+)?)\s*(?:c|cents?)\s*/\s*kwh",
            r"(?:usage|energy|flat|single)\s*(?:rate|charge|price)[^$]{0,100}\$(?P<value>\d+(?:\.\d+)?)\s*/\s*kwh",
        ],
        peak_patterns=[],
        shoulder_patterns=[],
        off_peak_patterns=[],
    ),
    TariffExtractionSpec(
        network_provider="evoenergy",
        tariff_code="RES-TOU",
        source_url="https://evoenergy.com.au/Your-Energy/Pricing-and-tariffs/Electricity-network-pricing",
        daily_patterns=[
            r"(?:daily|service|supply)\s+(?:charge|price)[^$c]{0,100}(?P<value>\d+(?:\.\d+)?)\s*(?:c|cents?)",
            r"(?:daily|service|supply)\s+(?:charge|price)[^$]{0,100}\$(?P<value>\d+(?:\.\d+)?)",
        ],
        usage_patterns=[],
        peak_patterns=[
            r"(?:peak)[^$c]{0,80}(?P<value>\d+(?:\.\d+)?)\s*(?:c|cents?)\s*/\s*kwh",
            r"(?:peak)[^$]{0,80}\$(?P<value>\d+(?:\.\d+)?)\s*/\s*kwh",
        ],
        shoulder_patterns=[],
        off_peak_patterns=[
            r"(?:off[\s-]*peak)[^$c]{0,80}(?P<value>\d+(?:\.\d+)?)\s*(?:c|cents?)\s*/\s*kwh",
            r"(?:off[\s-]*peak)[^$]{0,80}\$(?P<value>\d+(?:\.\d+)?)\s*/\s*kwh",
        ],
    ),
]


class TariffCatalogRefresher:
    def __init__(self, output_path: Path, timeout_s: float = 30.0, verbose: bool = False):
        self.output_path = output_path
        self.timeout_s = timeout_s
        self.verbose = verbose
        self._url_text_cache: dict[str, str] = {}

    def refresh(self, effective_from: Optional[str] = None) -> tuple[dict, list[str]]:
        payload = json.loads(self.output_path.read_text(encoding="utf-8"))
        tariffs = payload.get("tariffs", [])
        by_key: dict[tuple[str, str], dict] = {
            (item.get("network_provider", ""), item.get("tariff_code", "")): item for item in tariffs
        }
        logs: list[str] = []

        for baseline in BASELINE_TARIFFS:
            key = (baseline["network_provider"], baseline["tariff_code"])
            if key not in by_key:
                by_key[key] = json.loads(json.dumps(baseline))
                logs.append(f"[seed] {baseline['network_provider']}:{baseline['tariff_code']}")

        for spec in EXTRACTION_SPECS:
            key = (spec.network_provider, spec.tariff_code)
            existing = by_key.get(key)
            if not existing:
                logs.append(f"[skip] {spec.network_provider}:{spec.tariff_code}: missing from catalog and baseline")
                continue

            text = self._get_page_text(spec.source_url, logs)
            if text is None:
                logs.append(
                    f"[fallback] {spec.network_provider}:{spec.tariff_code}: failed to fetch source, keeping values"
                )
                continue

            updated = json.loads(json.dumps(existing))
            changed_fields: list[str] = []

            daily = _extract_cents(text, spec.daily_patterns)
            if daily is not None:
                updated["daily_supply_charge_cents"] = daily
                changed_fields.append("daily_supply_charge_cents")

            usage = _extract_cents(text, spec.usage_patterns)
            if usage is not None:
                updated["usage_rate_cents_per_kwh"] = usage
                changed_fields.append("usage_rate_cents_per_kwh")

            time_periods = {p.get("name"): p for p in updated.get("time_periods", [])}
            peak = _extract_cents(text, spec.peak_patterns)
            shoulder = _extract_cents(text, spec.shoulder_patterns)
            off_peak = _extract_cents(text, spec.off_peak_patterns)

            if peak is not None and "peak" in time_periods:
                time_periods["peak"]["rate_cents_per_kwh"] = peak
                changed_fields.append("time_periods.peak")
            if shoulder is not None and "shoulder" in time_periods:
                time_periods["shoulder"]["rate_cents_per_kwh"] = shoulder
                changed_fields.append("time_periods.shoulder")
            if off_peak is not None and "off_peak" in time_periods:
                time_periods["off_peak"]["rate_cents_per_kwh"] = off_peak
                changed_fields.append("time_periods.off_peak")

            if effective_from:
                updated["effective_from"] = effective_from
                changed_fields.append("effective_from")

            if changed_fields:
                updated["source_url"] = spec.source_url
                by_key[key] = updated
                logs.append(f"[updated] {spec.network_provider}:{spec.tariff_code}: {', '.join(changed_fields)}")
            else:
                logs.append(
                    f"[fallback] {spec.network_provider}:{spec.tariff_code}: no matching rates found, keeping values"
                )

        merged = list(by_key.values())
        merged.sort(key=lambda item: (item.get("network_provider", ""), item.get("tariff_code", "")))

        metadata = payload.get("metadata", {})
        baseline_sources = [item["source_url"] for item in BASELINE_TARIFFS if item.get("source_url")]
        spec_sources = [spec.source_url for spec in EXTRACTION_SPECS]
        merged_sources = list(dict.fromkeys([*metadata.get("sources", []), *baseline_sources, *spec_sources]))
        metadata["as_of"] = date.today().isoformat()
        metadata["sources"] = merged_sources
        metadata["description"] = "Curated network tariff snapshots sourced from public distributor/AER pages"
        payload["metadata"] = metadata
        payload["tariffs"] = merged
        return payload, logs

    def _get_page_text(self, url: str, logs: list[str]) -> Optional[str]:
        cached = self._url_text_cache.get(url)
        if cached is not None:
            return cached

        headers = {"User-Agent": "EnergyHubTariffRefresh/1.0 (+https://github.com/)"}
        try:
            with httpx.Client(timeout=self.timeout_s, follow_redirects=True, headers=headers) as client:
                response = client.get(url)
                response.raise_for_status()
        except Exception as exc:
            logs.append(f"[warn] fetch failed for {url}: {exc}")
            return None

        text = _clean_html_to_text(response.text)
        self._url_text_cache[url] = text
        if self.verbose:
            logs.append(f"[debug] fetched {url} ({len(text)} chars)")
        return text


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Refresh network tariff catalog from public sources.")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Path to network_tariffs.json (default: backend/app/data/network_tariffs.json)",
    )
    parser.add_argument(
        "--effective-from",
        default=None,
        help="Optional YYYY-MM-DD date to stamp on updated tariffs.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write updates to disk. Without this flag, run in dry-run mode.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print debug logs including fetched page sizes.",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    output_path = Path(args.output).resolve()
    refresher = TariffCatalogRefresher(output_path=output_path, timeout_s=args.timeout, verbose=args.verbose)
    payload, logs = refresher.refresh(effective_from=args.effective_from)

    for line in logs:
        print(line)

    if args.write:
        output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"[write] Updated catalog: {output_path}")
    else:
        print(f"[dry-run] No files written. Use --write to persist changes to {output_path}")


if __name__ == "__main__":
    main()
