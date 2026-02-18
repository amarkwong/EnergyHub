"""Invoice upload, parsing, and calculation endpoints."""
import uuid
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from typing import Optional
from sqlalchemy.orm import Session

from app.db.database import get_db, init_db
from app.models.auth import User
from app.schemas.invoice import (
    ParsedInvoice,
    CalculatedInvoice,
    InvoiceUploadResponse
)
from app.services.auth_service import auth_service, get_optional_current_user
from app.services.invoice_parser import InvoiceParser
from app.services.invoice_calculator import InvoiceCalculator

router = APIRouter()
invoice_parser = InvoiceParser()
invoice_calculator = InvoiceCalculator()


@router.post("/upload", response_model=InvoiceUploadResponse)
async def upload_invoice(
    file: UploadFile = File(...),
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload and parse an invoice PDF using OCR.

    The invoice will be parsed using Tesseract OCR to extract
    line items, amounts, and billing details.
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Expected PDF"
        )

    content = await file.read()
    file_id = str(uuid.uuid4())
    init_db()

    try:
        result = await invoice_parser.parse_invoice(file_id, content)
        invoice_parser.persist_invoice(
            db=db,
            file_id=file_id,
            invoice_data=result["invoice"],
            confidence=result["confidence"],
            warnings=result.get("warnings", []),
            user_id=user.id if user else None,
        )
        if user is not None:
            auth_service.apply_invoice_relationships(
                db=db,
                user=user,
                invoice_file_id=file_id,
                parsed_invoice=result["invoice"],
            )
        return InvoiceUploadResponse(
            file_id=file_id,
            filename=file.filename,
            parsed_invoice=result['invoice'],
            confidence_score=result['confidence'],
            warnings=result.get('warnings', [])
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse invoice: {str(e)}"
        )


@router.get("/{file_id}", response_model=ParsedInvoice)
async def get_parsed_invoice(file_id: str, db: Session = Depends(get_db)):
    """Get a previously parsed invoice by file ID."""
    invoice = await invoice_parser.get_invoice_with_fallback(file_id, db)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.post("/calculate", response_model=CalculatedInvoice)
async def calculate_invoice(
    nem12_file_id: str,
    network_tariff_code: str,
    retail_plan_name: Optional[str] = None,
    billing_start: str = None,
    billing_end: str = None
):
    """
    Calculate expected invoice based on consumption data and tariffs.

    Uses the NEM12 consumption data and specified tariffs to calculate
    what each line item should be.
    """
    try:
        calculated = await invoice_calculator.calculate(
            nem12_file_id=nem12_file_id,
            network_tariff_code=network_tariff_code,
            retail_plan_name=retail_plan_name,
            billing_start=billing_start,
            billing_end=billing_end
        )
        return calculated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Calculation failed: {str(e)}"
        )
