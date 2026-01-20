"""Invoice PDF parsing service using Tesseract OCR."""
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
import io

# These would be installed via requirements.txt
# import pytesseract
# from pdf2image import convert_from_bytes
# from PIL import Image


class InvoiceParser:
    """Service for parsing energy invoices from PDF using OCR."""

    def __init__(self):
        # In-memory storage (replace with database in production)
        self._invoices = {}

        # Common patterns for Australian energy invoices
        self._patterns = {
            'nmi': r'NMI[:\s]*(\d{10,11})',
            'invoice_number': r'(?:Invoice|Tax Invoice)[:\s#]*([A-Z0-9-]+)',
            'invoice_date': r'(?:Invoice Date|Date)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            'due_date': r'(?:Due Date|Payment Due)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            'total': r'(?:Total|Amount Due|Total Due)[:\s]*\$?([\d,]+\.?\d*)',
            'gst': r'(?:GST|Goods and Services Tax)[:\s]*\$?([\d,]+\.?\d*)',
            'billing_period': r'(?:Billing Period|Period)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s*(?:to|-)\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            'usage_kwh': r'(\d+(?:,\d+)?(?:\.\d+)?)\s*kWh',
            'rate': r'\$?([\d.]+)\s*(?:per|/)\s*kWh',
            'supply_charge': r'(?:Supply Charge|Daily Supply)[:\s]*\$?([\d.]+)\s*(?:per day|/day)?',
        }

    async def parse_invoice(self, file_id: str, pdf_content: bytes) -> dict:
        """
        Parse an invoice PDF using OCR.

        Returns parsed invoice data with confidence score.
        """
        # Extract text from PDF using OCR
        text = await self._extract_text_from_pdf(pdf_content)

        # Parse invoice details
        invoice_data = self._parse_invoice_text(text)

        # Calculate confidence based on how many fields were extracted
        confidence = self._calculate_confidence(invoice_data)

        warnings = []
        if confidence < 0.7:
            warnings.append("Low confidence extraction - please verify details")
        if not invoice_data.get('nmi'):
            warnings.append("NMI not found - please enter manually")

        # Store the parsed invoice
        self._invoices[file_id] = invoice_data

        return {
            'invoice': invoice_data,
            'confidence': confidence,
            'warnings': warnings
        }

    async def _extract_text_from_pdf(self, pdf_content: bytes) -> str:
        """Extract text from PDF using Tesseract OCR."""
        # Placeholder - actual implementation would use:
        # images = convert_from_bytes(pdf_content)
        # text = ""
        # for image in images:
        #     text += pytesseract.image_to_string(image)
        # return text

        # For now, return placeholder to allow testing
        return """
        Tax Invoice INV-2024-001234
        Invoice Date: 15/01/2024
        Due Date: 30/01/2024

        NMI: 12345678901
        Billing Period: 01/12/2023 to 31/12/2023

        Energy Usage
        Peak Usage: 450 kWh @ $0.35/kWh = $157.50
        Off-Peak Usage: 280 kWh @ $0.18/kWh = $50.40
        Supply Charge: 31 days @ $1.20/day = $37.20

        Network Charges
        Distribution: 730 kWh @ $0.08/kWh = $58.40

        Subtotal: $303.50
        GST: $30.35
        Total: $333.85
        """

    def _parse_invoice_text(self, text: str) -> dict:
        """Parse extracted text into structured invoice data."""
        from app.schemas.invoice import ChargeType

        # Extract basic fields
        nmi_match = re.search(self._patterns['nmi'], text)
        invoice_num_match = re.search(self._patterns['invoice_number'], text, re.IGNORECASE)
        invoice_date_match = re.search(self._patterns['invoice_date'], text, re.IGNORECASE)
        due_date_match = re.search(self._patterns['due_date'], text, re.IGNORECASE)
        billing_period_match = re.search(self._patterns['billing_period'], text, re.IGNORECASE)
        total_match = re.search(self._patterns['total'], text, re.IGNORECASE)
        gst_match = re.search(self._patterns['gst'], text, re.IGNORECASE)

        # Parse line items (simplified)
        line_items = self._parse_line_items(text)

        # Calculate subtotal
        subtotal = sum(item['amount'] for item in line_items if item['charge_type'] != 'gst')
        gst = Decimal(gst_match.group(1).replace(',', '')) if gst_match else Decimal('0')
        total = Decimal(total_match.group(1).replace(',', '')) if total_match else subtotal + gst

        return {
            'invoice_number': invoice_num_match.group(1) if invoice_num_match else 'Unknown',
            'invoice_date': self._parse_date(invoice_date_match.group(1)) if invoice_date_match else date.today(),
            'due_date': self._parse_date(due_date_match.group(1)) if due_date_match else None,
            'retailer': self._detect_retailer(text),
            'nmi': nmi_match.group(1) if nmi_match else None,
            'billing_period_start': self._parse_date(billing_period_match.group(1)) if billing_period_match else None,
            'billing_period_end': self._parse_date(billing_period_match.group(2)) if billing_period_match else None,
            'line_items': line_items,
            'subtotal': subtotal,
            'gst': gst,
            'total': total,
            'amount_due': total
        }

    def _parse_line_items(self, text: str) -> list[dict]:
        """Parse line items from invoice text."""
        items = []

        # Pattern for line items with quantity, rate, and amount
        line_pattern = r'(.+?):\s*(\d+(?:,\d+)?(?:\.\d+)?)\s*(?:kWh|days?)\s*@?\s*\$?([\d.]+)[/per\s]*(?:kWh|day)?\s*=?\s*\$?([\d,]+\.?\d*)'

        for match in re.finditer(line_pattern, text, re.IGNORECASE):
            description = match.group(1).strip()
            quantity = float(match.group(2).replace(',', ''))
            rate = Decimal(match.group(3))
            amount = Decimal(match.group(4).replace(',', ''))

            # Determine charge type from description
            charge_type = self._classify_charge(description)
            unit = 'day' if 'supply' in description.lower() or 'day' in description.lower() else 'kWh'

            items.append({
                'description': description,
                'charge_type': charge_type,
                'quantity': quantity,
                'unit': unit,
                'rate': rate,
                'amount': amount
            })

        return items

    def _classify_charge(self, description: str) -> str:
        """Classify a charge type from its description."""
        desc_lower = description.lower()

        if 'supply' in desc_lower or 'service' in desc_lower:
            return 'supply'
        elif 'network' in desc_lower or 'distribution' in desc_lower or 'transmission' in desc_lower:
            return 'network'
        elif 'demand' in desc_lower:
            return 'demand'
        elif 'meter' in desc_lower:
            return 'metering'
        elif 'green' in desc_lower or 'environmental' in desc_lower or 'rec' in desc_lower:
            return 'environmental'
        elif 'gst' in desc_lower:
            return 'gst'
        else:
            return 'usage'

    def _detect_retailer(self, text: str) -> str:
        """Detect retailer from invoice text."""
        retailers = [
            'AGL', 'Origin Energy', 'EnergyAustralia', 'Red Energy',
            'Simply Energy', 'Alinta Energy', 'Powershop', 'Momentum Energy'
        ]

        for retailer in retailers:
            if retailer.lower() in text.lower():
                return retailer

        return 'Unknown Retailer'

    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse date string to date object."""
        if not date_str:
            return None

        formats = ['%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y', '%d-%m-%y']
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue

        return None

    def _calculate_confidence(self, invoice_data: dict) -> float:
        """Calculate confidence score for parsed invoice."""
        required_fields = ['nmi', 'invoice_number', 'billing_period_start', 'billing_period_end', 'total']
        found = sum(1 for f in required_fields if invoice_data.get(f))

        # Base confidence from required fields
        confidence = found / len(required_fields)

        # Boost for having line items
        if invoice_data.get('line_items'):
            confidence = min(1.0, confidence + 0.1 * len(invoice_data['line_items']))

        return round(confidence, 2)

    async def get_invoice(self, file_id: str) -> Optional[dict]:
        """Retrieve a previously parsed invoice."""
        return self._invoices.get(file_id)
