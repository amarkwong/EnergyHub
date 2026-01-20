"""Invoice reconciliation endpoints."""
from fastapi import APIRouter, HTTPException

from app.schemas.reconciliation import (
    ReconciliationRequest,
    ReconciliationSummary,
    ReconciliationHistoryItem
)
from app.services.reconciliation_engine import ReconciliationEngine

router = APIRouter()
reconciliation_engine = ReconciliationEngine()


@router.post("/run", response_model=ReconciliationSummary)
async def run_reconciliation(request: ReconciliationRequest):
    """
    Run invoice reconciliation.

    Compares the parsed invoice against calculated values
    from NEM12 consumption data and tariffs. Returns a
    line-by-line breakdown of discrepancies.
    """
    try:
        result = await reconciliation_engine.reconcile(
            invoice_file_id=request.invoice_file_id,
            nem12_file_id=request.nem12_file_id,
            network_tariff_code=request.network_tariff_code,
            retail_plan_name=request.retail_plan_name,
            tolerance_percent=request.tolerance_percent
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Reconciliation failed: {str(e)}"
        )


@router.get("/{reconciliation_id}", response_model=ReconciliationSummary)
async def get_reconciliation(reconciliation_id: str):
    """Get a specific reconciliation result by ID."""
    result = await reconciliation_engine.get_reconciliation(reconciliation_id)
    if not result:
        raise HTTPException(status_code=404, detail="Reconciliation not found")
    return result


@router.get("/history/{nmi}", response_model=list[ReconciliationHistoryItem])
async def get_reconciliation_history(nmi: str, limit: int = 10):
    """Get reconciliation history for a specific NMI."""
    history = await reconciliation_engine.get_history(nmi, limit=limit)
    return history


@router.get("/export/{reconciliation_id}")
async def export_reconciliation(reconciliation_id: str, format: str = "csv"):
    """
    Export reconciliation results.

    Supported formats: csv, pdf
    """
    if format not in ["csv", "pdf"]:
        raise HTTPException(status_code=400, detail="Unsupported format")

    result = await reconciliation_engine.export(reconciliation_id, format)
    if not result:
        raise HTTPException(status_code=404, detail="Reconciliation not found")

    return result
