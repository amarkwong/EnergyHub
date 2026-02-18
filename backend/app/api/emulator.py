"""Plan emulator endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.database import SessionLocal
from app.models.auth import User, UserNmi
from app.schemas.emulator import EmulatorCompareRequest, EmulatorCompareResponse
from app.services.auth_service import get_current_user
from app.services.emulator_service import EmulatorService
from app.services.energy_expert_service import EnergyExpertService

router = APIRouter()
emulator_service = EmulatorService()


def _lookup_postcode(user_id: int, nmi: str) -> str | None:
    """Look up the postcode for a user's NMI."""
    with SessionLocal() as db:
        user_nmi = (
            db.query(UserNmi)
            .filter(UserNmi.user_id == user_id, UserNmi.nmi == nmi)
            .first()
        )
        return user_nmi.postcode if user_nmi else None


@router.post("/compare", response_model=EmulatorCompareResponse)
async def compare_plans(
    payload: EmulatorCompareRequest,
    user: User = Depends(get_current_user),
):
    """Compare all retail plans against actual meter data for a given NMI and billing period."""
    try:
        nmi = payload.nmi.strip().upper()
        postcode = _lookup_postcode(user.id, nmi)
        result = await emulator_service.compare_plans(
            nmi=nmi,
            billing_start=payload.billing_start,
            billing_end=payload.billing_end,
            user_id=user.id,
            retailer_filter=payload.retailer_filter,
            postcode=postcode,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Emulation failed: {str(e)}")


@router.get("/validate-catalog")
async def validate_catalog(
    user: User = Depends(get_current_user),
):
    """Audit the retail plan catalog for TOU rate duplicates and coverage issues."""
    catalog = emulator_service._load_plan_catalog()
    return EnergyExpertService.audit_catalog(catalog)
