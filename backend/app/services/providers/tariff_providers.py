"""Tariff and retail plan provider abstractions."""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Optional


@dataclass
class TariffPeriod:
    """Rate period for TOU plans."""

    name: str
    rate_cents_per_kwh: Decimal


@dataclass
class FeedInTariffComponent:
    """Feed-in tariff component, optionally tiered."""

    unit_price_cents_per_kwh: Decimal
    tier_min_kwh: Optional[Decimal]
    tier_max_kwh: Optional[Decimal]
    name: Optional[str]
    type: Optional[str]


@dataclass
class NetworkTariffModel:
    """Normalized network tariff model."""

    tariff_code: str
    tariff_name: str
    network_provider: str
    tariff_type: str
    effective_from: date
    daily_supply_charge_cents: Decimal
    usage_rate_cents_per_kwh: Optional[Decimal]
    time_periods: list[TariffPeriod]
    source_url: Optional[str]


@dataclass
class RetailPlanModel:
    """Normalized retail plan model."""

    retailer: str
    plan_name: str
    tariff_type: str
    effective_from: date
    daily_supply_charge_cents: Decimal
    usage_rate_cents_per_kwh: Optional[Decimal]
    time_periods: list[TariffPeriod]
    feed_in_tariffs: list[FeedInTariffComponent]
    source_url: Optional[str]


class NetworkTariffProvider(ABC):
    """Interface for retrieving network tariffs."""

    @abstractmethod
    async def get_tariff_by_code(self, tariff_code: str) -> Optional[NetworkTariffModel]:
        raise NotImplementedError


class RetailPlanProvider(ABC):
    """Interface for retrieving retailer plans."""

    @abstractmethod
    async def get_plan(self, plan_name: str, retailer: Optional[str] = None) -> Optional[RetailPlanModel]:
        raise NotImplementedError


class JsonCatalogTariffProvider(NetworkTariffProvider, RetailPlanProvider):
    """File-backed provider populated from curated web-sourced catalogs."""

    def __init__(
        self,
        network_tariffs_path: Optional[Path] = None,
        retail_plans_path: Optional[Path] = None,
    ):
        base = Path(__file__).resolve().parents[2]
        self._network_tariffs_path = network_tariffs_path or (base / "data" / "network_tariffs.json")
        self._retail_plans_path = retail_plans_path or (base / "data" / "retail_plans.json")
        self._network_cache: Optional[list[NetworkTariffModel]] = None
        self._retail_cache: Optional[list[RetailPlanModel]] = None

    async def get_tariff_by_code(self, tariff_code: str) -> Optional[NetworkTariffModel]:
        tariffs = self._load_network_tariffs()
        needle = tariff_code.strip().upper()
        for tariff in tariffs:
            if tariff.tariff_code.upper() == needle:
                return tariff
        return None

    async def get_plan(self, plan_name: str, retailer: Optional[str] = None) -> Optional[RetailPlanModel]:
        plans = self._load_retail_plans()
        plan_needle = plan_name.strip().lower()
        retailer_needle = retailer.strip().lower() if retailer else None

        for plan in plans:
            if plan.plan_name.strip().lower() != plan_needle:
                continue
            if retailer_needle and plan.retailer.strip().lower() != retailer_needle:
                continue
            return plan
        return None

    def _load_network_tariffs(self) -> list[NetworkTariffModel]:
        if self._network_cache is not None:
            return self._network_cache

        payload = json.loads(self._network_tariffs_path.read_text(encoding="utf-8"))
        tariffs: list[NetworkTariffModel] = []

        for item in payload.get("tariffs", []):
            periods = [
                TariffPeriod(
                    name=p["name"],
                    rate_cents_per_kwh=Decimal(str(p["rate_cents_per_kwh"])),
                )
                for p in item.get("time_periods", [])
            ]
            tariffs.append(
                NetworkTariffModel(
                    tariff_code=item["tariff_code"],
                    tariff_name=item["tariff_name"],
                    network_provider=item["network_provider"],
                    tariff_type=item["tariff_type"],
                    effective_from=date.fromisoformat(item["effective_from"]),
                    daily_supply_charge_cents=Decimal(str(item["daily_supply_charge_cents"])),
                    usage_rate_cents_per_kwh=Decimal(str(item["usage_rate_cents_per_kwh"]))
                    if item.get("usage_rate_cents_per_kwh") is not None
                    else None,
                    time_periods=periods,
                    source_url=item.get("source_url"),
                )
            )

        self._network_cache = tariffs
        return tariffs

    def _load_retail_plans(self) -> list[RetailPlanModel]:
        if self._retail_cache is not None:
            return self._retail_cache

        payload = json.loads(self._retail_plans_path.read_text(encoding="utf-8"))
        plans: list[RetailPlanModel] = []

        for item in payload.get("plans", []):
            periods = [
                TariffPeriod(
                    name=p["name"],
                    rate_cents_per_kwh=Decimal(str(p["rate_cents_per_kwh"])),
                )
                for p in item.get("time_periods", [])
            ]
            feed_in = [
                FeedInTariffComponent(
                    unit_price_cents_per_kwh=Decimal(str(p["unit_price_cents_per_kwh"])),
                    tier_min_kwh=Decimal(str(p["tier_min_kwh"])) if p.get("tier_min_kwh") is not None else None,
                    tier_max_kwh=Decimal(str(p["tier_max_kwh"])) if p.get("tier_max_kwh") is not None else None,
                    name=p.get("name"),
                    type=p.get("type"),
                )
                for p in item.get("feed_in_tariffs", [])
                if p.get("unit_price_cents_per_kwh") is not None
            ]
            plans.append(
                RetailPlanModel(
                    retailer=item["retailer"],
                    plan_name=item["plan_name"],
                    tariff_type=item["tariff_type"],
                    effective_from=date.fromisoformat(item["effective_from"]),
                    daily_supply_charge_cents=Decimal(str(item["daily_supply_charge_cents"])),
                    usage_rate_cents_per_kwh=Decimal(str(item["usage_rate_cents_per_kwh"]))
                    if item.get("usage_rate_cents_per_kwh") is not None
                    else None,
                    time_periods=periods,
                    feed_in_tariffs=feed_in,
                    source_url=item.get("source_url"),
                )
            )

        self._retail_cache = plans
        return plans
