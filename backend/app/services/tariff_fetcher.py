"""Tariff data fetching service for Australian network providers."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Optional

from app.schemas.tariff import NetworkProvider, TariffType


class TariffFetcher:
    """Service for reading normalized tariff snapshots from local catalogs."""

    def __init__(self, network_tariffs_path: Optional[Path] = None):
        base = Path(__file__).resolve().parents[1]
        self._network_tariffs_path = network_tariffs_path or (base / "data" / "network_tariffs.json")
        self._catalog_cache: Optional[dict] = None

    async def get_network_tariffs(
        self,
        provider: NetworkProvider,
        tariff_type: Optional[TariffType] = None,
        effective_date: Optional[date] = None,
    ) -> list[dict]:
        """Get network tariffs for a provider from the local catalog."""
        payload = self._load_catalog()
        tariffs = []
        target_date = effective_date or date.today()

        for item in payload.get("tariffs", []):
            if item.get("network_provider") != provider.value:
                continue
            if tariff_type and item.get("tariff_type") != tariff_type.value:
                continue

            effective_from = self._parse_date(item.get("effective_from"))
            effective_to = self._parse_date(item.get("effective_to"))
            if effective_from and target_date < effective_from:
                continue
            if effective_to and target_date > effective_to:
                continue

            tariffs.append(self._normalize_tariff_record(item))

        return tariffs

    async def get_network_tariff_history(self, provider: NetworkProvider) -> list[dict]:
        """Get all known tariffs for a provider grouped by effective year."""
        payload = self._load_catalog()
        grouped: dict[int, list[dict]] = {}

        for item in payload.get("tariffs", []):
            if item.get("network_provider") != provider.value:
                continue

            normalized = self._normalize_tariff_record(item)
            year = date.fromisoformat(normalized["effective_from"]).year
            grouped.setdefault(year, []).append(normalized)

        return [
            {"year": year, "tariffs": sorted(tariffs, key=lambda x: x["effective_from"], reverse=True)}
            for year, tariffs in sorted(grouped.items(), reverse=True)
        ]

    async def get_tariff_by_code(
        self,
        provider: Optional[NetworkProvider],
        tariff_code: str,
    ) -> Optional[dict]:
        """Get detailed tariff information by code."""
        payload = self._load_catalog()
        needle = tariff_code.strip().upper()

        for item in payload.get("tariffs", []):
            if provider and item.get("network_provider") != provider.value:
                continue
            if item.get("tariff_code", "").strip().upper() != needle:
                continue

            return {
                "network_tariff": self._normalize_tariff_record(item),
                "last_updated": date.today().isoformat(),
                "source_url": item.get("source_url"),
            }

        return None

    async def refresh_provider_tariffs(self, provider: NetworkProvider) -> None:
        """Clear catalog cache so subsequent reads reflect updated files."""
        del provider  # provider-specific refresh can be implemented with live ingestion.
        self._catalog_cache = None

    def _load_catalog(self) -> dict:
        if self._catalog_cache is None:
            self._catalog_cache = json.loads(self._network_tariffs_path.read_text(encoding="utf-8"))
        return self._catalog_cache

    def _normalize_tariff_record(self, item: dict) -> dict:
        record = {
            "tariff_code": item["tariff_code"],
            "tariff_name": item["tariff_name"],
            "network_provider": item["network_provider"],
            "tariff_type": item["tariff_type"],
            "effective_from": item["effective_from"],
            "effective_to": item.get("effective_to"),
            "daily_supply_charge_cents": item["daily_supply_charge_cents"],
        }

        usage_rate = item.get("usage_rate_cents_per_kwh")
        if usage_rate is not None:
            record["usage_rate_cents_per_kwh"] = usage_rate

        demand_rate = item.get("demand_rate_cents_per_kw")
        if demand_rate is not None:
            record["demand_rate_cents_per_kw"] = demand_rate

        if item.get("time_periods"):
            record["time_periods"] = [self._normalize_period(p) for p in item["time_periods"]]

        return record

    def _normalize_period(self, period: dict) -> dict:
        return {
            "name": period["name"],
            "start_time": period.get("start_time"),
            "end_time": period.get("end_time"),
            "days": period.get("days", [0, 1, 2, 3, 4, 5, 6]),
            "rate_cents_per_kwh": period["rate_cents_per_kwh"],
        }

    @staticmethod
    def _parse_date(value: Optional[str]) -> Optional[date]:
        if not value:
            return None
        return date.fromisoformat(value)
