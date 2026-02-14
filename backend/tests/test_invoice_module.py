"""Invoice calculator and parser integration-focused tests."""
from decimal import Decimal
import json
from pathlib import Path

import pytest

from app.services.invoice_calculator import InvoiceCalculator
from app.services.invoice_parser import InvoiceParser
from app.services.nem12_service import NEM12Service
from app.services.providers.tariff_providers import JsonCatalogTariffProvider
from app.services.providers.tariff_providers import FeedInTariffComponent
from app.services.retailer_csv_meter_service import RetailerCsvMeterService
from app.db.database import SessionLocal
from app.services.reconciliation_engine import ReconciliationEngine


FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
async def test_tariff_provider_loads_network_and_retail_catalogs():
    provider = JsonCatalogTariffProvider()

    network = await provider.get_tariff_by_code("EA025")
    retail_payload = json.loads((Path(__file__).parents[1] / "app" / "data" / "retail_plans.json").read_text(encoding="utf-8"))
    first_plan = retail_payload["plans"][0]
    retail = await provider.get_plan(first_plan["plan_name"], retailer=first_plan["retailer"])

    assert network is not None
    assert network.network_provider == "ausgrid"
    assert retail is not None
    assert retail.retailer == first_plan["retailer"]


@pytest.mark.asyncio
async def test_calculator_uses_provider_rates_for_output():
    nem12 = NEM12Service()
    content = (FIXTURE_DIR / "nem12_30m.csv").read_text(encoding="utf-8")
    file_id = "invoice-calc-fixture"
    await nem12.process_nem12(file_id, content)

    retail_payload = json.loads((Path(__file__).parents[1] / "app" / "data" / "retail_plans.json").read_text(encoding="utf-8"))
    first_plan = retail_payload["plans"][0]

    calculator = InvoiceCalculator()
    result = await calculator.calculate(
        nem12_file_id=file_id,
        network_tariff_code="EA025",
        retail_plan_name=first_plan["plan_name"],
    )

    assert result["total"] > 0
    descriptions = [item["description"] for item in result["line_items"]]
    assert any("Network" in d for d in descriptions)
    assert any("Retail" in d for d in descriptions)
    assert "source" in result["calculation_notes"].lower() or "http" in result["calculation_notes"].lower()


@pytest.mark.asyncio
async def test_parser_extracts_fields_from_realistic_invoice_text(monkeypatch):
    sample_text = """
    AGL Tax Invoice INV-2024-001234
    Invoice Date: 15/01/2024
    Due Date: 30/01/2024
    NMI: 12345678901
    Billing Period: 01/12/2023 to 31/12/2023
    Peak Usage: 450 kWh @ $0.35/kWh = $157.50
    Off-Peak Usage: 280 kWh @ $0.18/kWh = $50.40
    Supply Charge: 31 days @ $1.20/day = $37.20
    GST: $24.51
    Total: $269.61
    """

    async def fake_extract(_pdf_bytes: bytes) -> str:
        return sample_text

    parser = InvoiceParser()
    monkeypatch.setattr(parser, "_extract_text_from_pdf", fake_extract)

    result = await parser.parse_invoice("sample", b"%PDF")
    invoice = result["invoice"]

    assert invoice["invoice_number"] == "INV-2024-001234"
    assert invoice["nmi"] == "12345678901"
    assert invoice["retailer"] == "AGL"
    assert invoice["total"] > 0
    assert len(invoice["line_items"]) >= 3
    assert result["confidence"] >= 0.7


@pytest.mark.asyncio
async def test_parser_handles_agl_embedded_text_style(monkeypatch):
    sample_text = """
    037/99871
    Issue date
    10 Feb 2026
    Service address: 12 Example Street, Brisbane QLD 4000
    National Metering Identifier (NMI)
    31201328846
    Tax Invoice
    Need help?
    Bill period: 9 Jan 2026 to 8 Feb 2026 (31 days)
    101.875 kWh $0.3136 $31.95At all timesGeneral usage
    0.027 kWh $0.1691 $0.00At all timesTariff 31 controlled load
    31 days $1.2226 $37.90DailySupply charge
    31 days $0.00 $0.00DailyCL31 supply charge
    Standard feed-in tariff* At all times 310 kWh $0.1 $31.00cr
    Next* At all times 699.36 kWh $0.03 $20.98cr
    Direct Debit amount due = $24.86
    """

    async def fake_extract(_pdf_bytes: bytes) -> str:
        return sample_text

    parser = InvoiceParser()
    monkeypatch.setattr(parser, "_extract_text_from_pdf", fake_extract)

    result = await parser.parse_invoice("sample-agl", b"%PDF")
    invoice = result["invoice"]

    assert invoice["invoice_number"] == "037/99871"
    assert invoice["nmi"] == "31201328846"
    assert invoice["service_address"] == "12 Example Street, Brisbane QLD 4000"
    assert invoice["service_state"] == "QLD"
    assert invoice["service_postcode"] == "4000"
    assert str(invoice["billing_period_start"]) == "2026-01-09"
    assert str(invoice["billing_period_end"]) == "2026-02-08"
    by_desc = {item["description"]: item for item in invoice["line_items"]}
    assert "General usage" in by_desc
    assert by_desc["General usage"]["quantity"] == 101.875
    assert str(by_desc["General usage"]["rate"]) == "0.3136"
    assert str(by_desc["General usage"]["amount"]) == "31.95"
    assert "Standard feed-in tariff*" in by_desc
    assert str(by_desc["Standard feed-in tariff*"]["amount"]) == "-31.00"


@pytest.mark.asyncio
async def test_calculator_uses_invoice_context_for_line_items():
    # Build interval rows via retailer CSV ingestion with General, Controlled load and Solar.
    content = """AccountNumber,NMI,DeviceNumber,DeviceType,RegisterCode,RateTypeDescription,StartDate,EndDate,ProfileReadValue,RegisterReadValue,QualityFlag
7086,31201328846,EDA1,COMMS4D,10309#E1,Generalusage,09/01/2026 12:00:00 AM,09/01/2026 12:29:59 AM,101.875,0,A
7086,31201328846,EDA1,COMMS4D,10309#E2,Controlledload,09/01/2026 12:00:00 AM,09/01/2026 12:29:59 AM,0.027,0,A
7086,31201328846,EDA1,COMMS4D,10309#B1,Solar,09/01/2026 12:00:00 AM,09/01/2026 12:29:59 AM,1009.36,0,A
"""
    with SessionLocal() as db:
        RetailerCsvMeterService().ingest(db, file_id="invoice-context-meter", content=content)

    calculator = InvoiceCalculator()
    parsed_invoice = {
        "nmi": "31201328846",
        "billing_period_start": "2026-01-09",
        "billing_period_end": "2026-01-09",
        "energy_plan_name": "Solar Savers 1",
        "line_items": [
            {"description": "General usage", "charge_type": "usage", "quantity": 101.875, "unit": "kWh", "rate": "0.3136", "amount": "31.95"},
            {"description": "Tariff 31 controlled load", "charge_type": "usage", "quantity": 0.027, "unit": "kWh", "rate": "0.1691", "amount": "0.00"},
            {"description": "Supply charge", "charge_type": "supply", "quantity": 1, "unit": "day", "rate": "1.2226", "amount": "1.22"},
            {"description": "Standard feed-in tariff*", "charge_type": "usage", "quantity": 1009.36, "unit": "kWh", "rate": "0.10", "amount": "-100.94"},
            {"description": "Total GST +", "charge_type": "gst", "quantity": None, "unit": None, "rate": None, "amount": "3.32"},
        ],
    }
    out = await calculator.calculate(
        nem12_file_id="invoice-context-meter",
        parsed_invoice=parsed_invoice,
    )
    by_desc = {item["description"]: item for item in out["line_items"]}
    assert by_desc["General usage"]["amount"] > 0
    assert by_desc["Supply charge"]["amount"] > 0
    assert by_desc["Standard feed-in tariff*"]["amount"] < 0


@pytest.mark.asyncio
async def test_calculator_uses_invoice_feed_in_split_when_plan_tiers_missing():
    content = """AccountNumber,NMI,DeviceNumber,DeviceType,RegisterCode,RateTypeDescription,StartDate,EndDate,ProfileReadValue,RegisterReadValue,QualityFlag
7086,31201328846,EDA1,COMMS4D,10309#E1,Generalusage,09/01/2026 12:00:00 AM,09/01/2026 12:29:59 AM,101.875,0,A
7086,31201328846,EDA1,COMMS4D,10309#B1,Solar,09/01/2026 12:00:00 AM,09/01/2026 12:29:59 AM,1009.36,0,A
"""
    with SessionLocal() as db:
        RetailerCsvMeterService().ingest(db, file_id="invoice-context-fit-split", content=content)

    calculator = InvoiceCalculator()
    parsed_invoice = {
        "nmi": "31201328846",
        "billing_period_start": "2026-01-09",
        "billing_period_end": "2026-02-08",
        "retailer": "AGL",
        "energy_plan_name": "Residential Solar Savers",
        "line_items": [
            {"description": "Standard feed-in tariff*", "charge_type": "usage", "quantity": 310, "unit": "kWh", "rate": "0.10", "amount": "-31.00"},
            {"description": "Next*", "charge_type": "usage", "quantity": 699.36, "unit": "kWh", "rate": "0.03", "amount": "-20.98"},
        ],
    }
    out = await calculator.calculate(
        nem12_file_id="invoice-context-fit-split",
        parsed_invoice=parsed_invoice,
    )
    by_desc = {item["description"]: item for item in out["line_items"]}
    assert str(by_desc["Standard feed-in tariff*"]["quantity"]) == "-310.0"
    assert str(by_desc["Next*"]["quantity"]) == "-699.36"
    assert str(by_desc["Standard feed-in tariff*"]["amount"]) == "-31.00"
    assert str(by_desc["Next*"]["amount"]) == "-20.98"


def test_feed_in_split_first_10kwh_per_day():
    components = [
        FeedInTariffComponent(
            unit_price_cents_per_kwh=Decimal("10"),
            tier_min_kwh=Decimal("0"),
            tier_max_kwh=Decimal("10"),
            name="For the first 10kwh",
            type=None,
        ),
        FeedInTariffComponent(
            unit_price_cents_per_kwh=Decimal("3"),
            tier_min_kwh=Decimal("10"),
            tier_max_kwh=None,
            name="Next",
            type=None,
        ),
    ]
    first_kwh, next_kwh = InvoiceCalculator._compute_feed_in_split(
        total_export_kwh=Decimal("1009.36"),
        billing_days=31,
        components=components,
    )
    assert first_kwh == Decimal("310")
    assert next_kwh == Decimal("699.36")


def test_reconcile_line_items_matches_by_type_index():
    engine = ReconciliationEngine()
    invoiced = [
        {"description": "Supply charge", "charge_type": "supply", "amount": "37.90"},
        {"description": "Total GST +", "charge_type": "gst", "amount": "6.99"},
    ]
    calculated = [
        {"description": "Supply charge", "charge_type": "supply", "amount": "37.90"},
        {"description": "GST", "charge_type": "gst", "amount": "6.99"},
    ]
    rows = engine._reconcile_line_items(invoiced, calculated, tolerance_percent=1.0)
    status_by_desc = {r["description"]: r["status"] for r in rows}
    assert status_by_desc["Supply charge"] == "match"
    assert status_by_desc["Total GST +"] == "match"
