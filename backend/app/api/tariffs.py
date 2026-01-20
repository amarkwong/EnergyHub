"""Tariff data endpoints."""
from datetime import date
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from app.schemas.tariff import (
    NetworkProvider,
    TariffType,
    NetworkTariff,
    RetailTariff,
    TariffSearchRequest,
    TariffResponse
)
from app.services.tariff_fetcher import TariffFetcher

router = APIRouter()
tariff_fetcher = TariffFetcher()


@router.get("/network-providers")
async def list_network_providers():
    """
    List all supported network providers.

    Returns the list of Australian electricity distributors
    that we can fetch tariff data for.
    """
    return [
        {"code": p.value, "name": p.name.replace("_", " ").title(), "state": _get_state(p)}
        for p in NetworkProvider
    ]


def _get_state(provider: NetworkProvider) -> str:
    """Get state for a network provider."""
    state_map = {
        NetworkProvider.EVOENERGY: "ACT",
        NetworkProvider.ERGON_ENERGY: "QLD",
        NetworkProvider.ENERGEX: "QLD",
        NetworkProvider.AUSGRID: "NSW",
        NetworkProvider.ESSENTIAL_ENERGY: "NSW",
        NetworkProvider.ENDEAVOUR_ENERGY: "NSW",
        NetworkProvider.AUSNET_SERVICES: "VIC",
        NetworkProvider.POWERCOR: "VIC",
        NetworkProvider.JEMENA: "VIC",
        NetworkProvider.CITIPOWER: "VIC",
        NetworkProvider.UNITED_ENERGY: "VIC",
        NetworkProvider.TASNETWORKS: "TAS",
    }
    return state_map.get(provider, "Unknown")


@router.get("/network/{provider}", response_model=list[NetworkTariff])
async def get_network_tariffs(
    provider: NetworkProvider,
    tariff_type: Optional[TariffType] = None,
    effective_date: Optional[date] = Query(default=None)
):
    """
    Get network tariffs for a specific provider.

    Fetches the latest tariff data from the network provider's
    published tariff schedules.
    """
    try:
        tariffs = await tariff_fetcher.get_network_tariffs(
            provider=provider,
            tariff_type=tariff_type,
            effective_date=effective_date or date.today()
        )
        return tariffs
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch tariffs: {str(e)}"
        )


@router.get("/network/{provider}/{tariff_code}", response_model=TariffResponse)
async def get_tariff_details(provider: NetworkProvider, tariff_code: str):
    """Get detailed tariff information by code."""
    tariff = await tariff_fetcher.get_tariff_by_code(provider, tariff_code)
    if not tariff:
        raise HTTPException(status_code=404, detail="Tariff not found")
    return tariff


@router.post("/refresh/{provider}")
async def refresh_tariffs(provider: NetworkProvider):
    """
    Force refresh tariff data from provider.

    Clears the cache and fetches fresh tariff data.
    """
    try:
        await tariff_fetcher.refresh_provider_tariffs(provider)
        return {"status": "refreshed", "provider": provider.value}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh tariffs: {str(e)}"
        )
