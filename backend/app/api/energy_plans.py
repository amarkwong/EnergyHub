"""Energy plan catalog endpoints (catalog-backed)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from app.schemas.energy_plan import (
    CatalogPlanOut,
    CatalogRetailerOut,
    CatalogStatusOut,
)
from app.services.catalog_service import get_catalog

router = APIRouter()


@router.get("/status", response_model=CatalogStatusOut)
def catalog_status():
    """Return catalog metadata (last build time, counts)."""
    meta = get_catalog().get_metadata()
    return CatalogStatusOut(
        version=meta.get("version"),
        generated_at_utc=meta.get("generated_at_utc"),
        retailer_count=meta.get("retailer_count", 0),
        plan_count=meta.get("plan_count", 0),
        postcode_count=meta.get("postcode_count", 0),
    )


@router.get("/retailers", response_model=list[CatalogRetailerOut])
def list_retailers():
    """List all retailers from the pre-built catalog."""
    return [
        CatalogRetailerOut(
            slug=r["slug"],
            name=r["name"],
            states=r.get("states", []),
        )
        for r in get_catalog().get_retailers()
    ]


@router.get("/plans", response_model=list[CatalogPlanOut])
def list_plans(
    retailer_slug: Optional[str] = Query(default=None),
    postcode: Optional[str] = Query(default=None),
):
    """List plans, optionally filtered by retailer and/or postcode."""
    catalog = get_catalog()

    if postcode and retailer_slug:
        plans = [
            p for p in catalog.get_plans_for_postcode(postcode)
            if p.get("retailer_slug") == retailer_slug
        ]
    elif postcode:
        plans = catalog.get_plans_for_postcode(postcode)
    elif retailer_slug:
        plans = catalog.get_plans_for_retailer(retailer_slug)
    else:
        plans = catalog.get_all_plans()

    return [_to_plan_out(p) for p in plans]


@router.get("/plans/{idx}", response_model=CatalogPlanOut)
def get_plan(idx: int):
    """Get a single plan by its catalog index."""
    plan = get_catalog().get_plan_by_idx(idx)
    if plan is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Plan idx={idx} not found")
    return _to_plan_out(plan)


def _to_plan_out(plan: dict) -> CatalogPlanOut:
    return CatalogPlanOut(**plan)
