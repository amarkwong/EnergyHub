"""Energy plan and TOU catalog endpoints."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db, init_db
from app.models.energy_plan import EnergyPlan, TouDefinition
from app.schemas.energy_plan import (
    EmeFetchAllRetailersRequest,
    EmeFetchAllRetailersResponse,
    EmeFetchRegistryRequest,
    EmeFetchRequest,
    EmeFetchResponse,
    EnergyPlanOut,
    EnergyPlanRefreshResponse,
    RetailerOut,
    TouDefinitionOut,
    TouPeriodOut,
)
from app.services.eme_plan_fetch_service import (
    DEFAULT_EME_OUTPUT_PATH,
    DEFAULT_RETAIL_CATALOG_PATH,
    EmePlanFetchService,
    SEMIANNUAL_EVENTBRIDGE_CRON,
)
from app.services.energy_plan_service import EnergyPlanService
from scripts.fetch_tariffs import TariffCatalogRefresher


router = APIRouter()
service = EnergyPlanService()
eme_fetch_service = EmePlanFetchService()


def _ensure_seeded(db: Session) -> None:
    init_db()
    if service.list_retailers(db):
        return
    service.refresh_catalogs(db)


def _refresh_network_tariffs_catalog() -> int:
    network_catalog = Path(DEFAULT_RETAIL_CATALOG_PATH).parents[0] / "network_tariffs.json"
    refresher = TariffCatalogRefresher(output_path=network_catalog, timeout_s=30.0, verbose=False)
    payload, logs = refresher.refresh()
    network_catalog.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return len(logs)


@router.post("/refresh", response_model=EnergyPlanRefreshResponse)
def refresh_energy_plan_catalog(db: Session = Depends(get_db)):
    """Refresh retailers, plans, and TOU definitions into DB."""
    try:
        init_db()
        result = service.refresh_catalogs(db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to refresh plan catalog: {exc}") from exc
    return EnergyPlanRefreshResponse(**result)


@router.post("/fetch-eme", response_model=EmeFetchResponse)
def fetch_eme_and_optionally_refresh(
    payload: EmeFetchRequest,
    db: Session = Depends(get_db),
):
    """Fetch latest plans from EME CDR and optionally persist+refresh local catalog."""
    try:
        init_db()
        retailers = [item.strip() for item in payload.retailers if item.strip()]
        if not retailers:
            raise HTTPException(status_code=400, detail="retailers must contain at least one non-empty slug")

        eme_payload = eme_fetch_service.fetch_to_file(
            retailers=retailers,
            output_path=Path(DEFAULT_EME_OUTPUT_PATH),
            page_size=payload.page_size,
            max_plans=payload.max_plans_per_retailer,
            fuel_type=payload.fuel_type,
            timeout_seconds=payload.timeout_seconds,
        )

        catalog_stats = None
        db_refresh = None
        network_log_lines = None
        network_refreshed = False
        persisted = False
        if payload.persist_to_retail_catalog:
            catalog_stats = eme_fetch_service.persist_retail_catalog(
                eme_payload=eme_payload,
                retail_catalog_path=Path(DEFAULT_RETAIL_CATALOG_PATH),
            )
            persisted = True
            if payload.refresh_db_after_persist:
                refresh_result = service.refresh_catalogs(db)
                db_refresh = EnergyPlanRefreshResponse(**refresh_result)
        if payload.refresh_network_tariffs:
            network_log_lines = _refresh_network_tariffs_catalog()
            network_refreshed = True

        return EmeFetchResponse(
            output_file=str(DEFAULT_EME_OUTPUT_PATH),
            plans_fetched=len(eme_payload.get("plans", [])),
            retailers_requested=len(retailers),
            stats=eme_payload.get("stats", {}),
            retail_catalog_persisted=persisted,
            retail_catalog_file=str(DEFAULT_RETAIL_CATALOG_PATH) if persisted else None,
            retail_catalog_stats=catalog_stats,
            db_refresh=db_refresh,
            cadence_months=6,
            recommended_eventbridge_cron=SEMIANNUAL_EVENTBRIDGE_CRON,
            next_recommended_run_utc=eme_fetch_service.next_semiannual_run_utc().isoformat(),
            network_tariffs_refreshed=network_refreshed,
            network_tariff_log_lines=network_log_lines,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch EME plans: {exc}") from exc


@router.post("/fetch-eme-all-retailers", response_model=EmeFetchAllRetailersResponse)
def fetch_eme_all_retailers(
    payload: EmeFetchAllRetailersRequest,
    db: Session = Depends(get_db),
):
    """Fetch EME plans for all retailers extracted from dropdown HTML."""
    try:
        init_db()
        eme_payload = eme_fetch_service.fetch_from_dropdown_html(
            dropdown_html=payload.dropdown_html,
            source_url=payload.source_url,
            output_path=Path(DEFAULT_EME_OUTPUT_PATH),
            page_size=payload.page_size,
            max_plans=payload.max_plans_per_retailer,
            fuel_type=payload.fuel_type,
            timeout_seconds=payload.timeout_seconds,
        )

        catalog_stats = None
        db_refresh = None
        network_log_lines = None
        network_refreshed = False
        persisted = False
        if payload.persist_to_retail_catalog:
            catalog_stats = eme_fetch_service.persist_retail_catalog(
                eme_payload=eme_payload,
                retail_catalog_path=Path(DEFAULT_RETAIL_CATALOG_PATH),
            )
            persisted = True
            if payload.refresh_db_after_persist:
                refresh_result = service.refresh_catalogs(db)
                db_refresh = EnergyPlanRefreshResponse(**refresh_result)
        if payload.refresh_network_tariffs:
            network_log_lines = _refresh_network_tariffs_catalog()
            network_refreshed = True

        resolved = eme_payload.get("resolved_retailers", [])
        unresolved = eme_payload.get("unresolved_retailers", [])
        return EmeFetchAllRetailersResponse(
            output_file=str(DEFAULT_EME_OUTPUT_PATH),
            retailers_discovered=int(eme_payload.get("metadata", {}).get("retailers_discovered", 0)),
            retailers_resolved=len(resolved),
            retailers_unresolved=len(unresolved),
            resolved_retailers=resolved,
            unresolved_retailers=unresolved,
            plans_fetched=len(eme_payload.get("plans", [])),
            stats=eme_payload.get("stats", {}),
            retail_catalog_persisted=persisted,
            retail_catalog_file=str(DEFAULT_RETAIL_CATALOG_PATH) if persisted else None,
            retail_catalog_stats=catalog_stats,
            db_refresh=db_refresh,
            cadence_months=6,
            recommended_eventbridge_cron=SEMIANNUAL_EVENTBRIDGE_CRON,
            next_recommended_run_utc=eme_fetch_service.next_semiannual_run_utc().isoformat(),
            network_tariffs_refreshed=network_refreshed,
            network_tariff_log_lines=network_log_lines,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch all EME retailers: {exc}") from exc


@router.post("/fetch-eme-registry", response_model=EmeFetchAllRetailersResponse)
def fetch_eme_registry(
    payload: EmeFetchRegistryRequest,
    db: Session = Depends(get_db),
):
    """Fetch EME plans for all CDR-registered retailers from the jxeeno registry."""
    try:
        init_db()
        eme_payload = eme_fetch_service.fetch_from_registry(
            registry_url=payload.registry_url,
            output_path=Path(DEFAULT_EME_OUTPUT_PATH),
            page_size=payload.page_size,
            max_plans=payload.max_plans_per_retailer,
            fuel_type=payload.fuel_type,
            timeout_seconds=payload.timeout_seconds,
        )

        catalog_stats = None
        db_refresh = None
        network_log_lines = None
        network_refreshed = False
        persisted = False
        if payload.persist_to_retail_catalog:
            catalog_stats = eme_fetch_service.persist_retail_catalog(
                eme_payload=eme_payload,
                retail_catalog_path=Path(DEFAULT_RETAIL_CATALOG_PATH),
            )
            persisted = True
            if payload.refresh_db_after_persist:
                refresh_result = service.refresh_catalogs(db)
                db_refresh = EnergyPlanRefreshResponse(**refresh_result)
        if payload.refresh_network_tariffs:
            network_log_lines = _refresh_network_tariffs_catalog()
            network_refreshed = True

        resolved = eme_payload.get("resolved_retailers", [])
        unresolved = eme_payload.get("unresolved_retailers", [])
        return EmeFetchAllRetailersResponse(
            output_file=str(DEFAULT_EME_OUTPUT_PATH),
            retailers_discovered=int(eme_payload.get("metadata", {}).get("retailers_discovered", 0)),
            retailers_resolved=len(resolved),
            retailers_unresolved=len(unresolved),
            resolved_retailers=resolved,
            unresolved_retailers=unresolved,
            plans_fetched=len(eme_payload.get("plans", [])),
            stats=eme_payload.get("stats", {}),
            retail_catalog_persisted=persisted,
            retail_catalog_file=str(DEFAULT_RETAIL_CATALOG_PATH) if persisted else None,
            retail_catalog_stats=catalog_stats,
            db_refresh=db_refresh,
            cadence_months=6,
            recommended_eventbridge_cron=SEMIANNUAL_EVENTBRIDGE_CRON,
            next_recommended_run_utc=eme_fetch_service.next_semiannual_run_utc().isoformat(),
            network_tariffs_refreshed=network_refreshed,
            network_tariff_log_lines=network_log_lines,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch from CDR registry: {exc}") from exc


@router.get("/retailers", response_model=list[RetailerOut])
def list_retailers(db: Session = Depends(get_db)):
    _ensure_seeded(db)
    retailers = service.list_retailers(db)
    return [RetailerOut(id=r.id, name=r.name, slug=r.slug, source_url=r.source_url) for r in retailers]


@router.get("/plans", response_model=list[EnergyPlanOut])
def list_energy_plans(
    retailer_slug: Optional[str] = Query(default=None),
    network_provider: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    _ensure_seeded(db)
    plans = service.list_energy_plans(db, retailer_slug=retailer_slug, network_provider=network_provider)
    return [_serialize_plan(p) for p in plans]


@router.get("/tou-definitions", response_model=list[TouDefinitionOut])
def list_tou_definitions(
    scope_type: Optional[str] = Query(default=None),
    scope_key: Optional[str] = Query(default=None),
    effective_date: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
):
    _ensure_seeded(db)
    definitions = service.list_tou_definitions(db, scope_type=scope_type, scope_key=scope_key)
    if effective_date:
        definitions = [
            d
            for d in definitions
            if d.effective_from <= effective_date and (d.effective_to is None or d.effective_to >= effective_date)
        ]
    return [_serialize_definition(d) for d in definitions]


@router.get("/history")
def list_energy_plan_history(
    retailer_slug: Optional[str] = Query(default=None),
    network_provider: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """Get historical plan and TOU definitions grouped by effective year."""
    _ensure_seeded(db)
    plans = service.list_energy_plans(db, retailer_slug=retailer_slug, network_provider=network_provider)
    definitions = service.list_tou_definitions(db, scope_type="retailer", scope_key=retailer_slug) if retailer_slug else []

    grouped: dict[int, dict] = {}
    for plan in plans:
        year = plan.effective_from.year
        bucket = grouped.setdefault(year, {"year": year, "plans": [], "tou_definitions": []})
        bucket["plans"].append(_serialize_plan(plan).model_dump())

    for definition in definitions:
        year = definition.effective_from.year
        bucket = grouped.setdefault(year, {"year": year, "plans": [], "tou_definitions": []})
        bucket["tou_definitions"].append(_serialize_definition(definition).model_dump())

    return [grouped[y] for y in sorted(grouped.keys(), reverse=True)]


def _serialize_plan(plan: EnergyPlan) -> EnergyPlanOut:
    import json as _json
    feed_in_tariffs: list[dict] = []
    if plan.feed_in_tariffs_json:
        try:
            feed_in_tariffs = _json.loads(plan.feed_in_tariffs_json)
        except (ValueError, TypeError):
            pass
    return EnergyPlanOut(
        id=plan.id,
        retailer=plan.retailer.name,
        retailer_slug=plan.retailer.slug,
        plan_name=plan.plan_name,
        network_provider=plan.network_provider,
        tariff_type=plan.tariff_type,
        effective_from=plan.effective_from,
        effective_to=plan.effective_to,
        daily_supply_charge_cents=plan.daily_supply_charge_cents,
        usage_rate_cents_per_kwh=plan.usage_rate_cents_per_kwh,
        feed_in_tariff_cents_per_kwh=plan.feed_in_tariff_cents_per_kwh,
        feed_in_tariffs=feed_in_tariffs,
        source_url=plan.source_url,
        is_active=plan.is_active,
    )


def _serialize_definition(definition: TouDefinition) -> TouDefinitionOut:
    periods = []
    for p in sorted(definition.periods, key=lambda x: x.priority):
        days = [int(v) for v in p.days_of_week.split(",") if v != ""]
        periods.append(
            TouPeriodOut(
                id=p.id,
                name=p.name,
                start_time=p.start_time,
                end_time=p.end_time,
                days_of_week=days,
                rate_cents_per_kwh=p.rate_cents_per_kwh,
                demand_rate_cents_per_kva=p.demand_rate_cents_per_kva,
                unit=p.unit,
                priority=p.priority,
            )
        )
    return TouDefinitionOut(
        id=definition.id,
        scope_type=definition.scope_type,
        scope_key=definition.scope_key,
        name=definition.name,
        timezone=definition.timezone,
        source_url=definition.source_url,
        effective_from=definition.effective_from,
        effective_to=definition.effective_to,
        plan_id=definition.plan_id,
        periods=periods,
    )
