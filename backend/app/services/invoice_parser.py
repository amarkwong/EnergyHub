"""Invoice PDF parsing service using OCR with fallbacks."""
import io
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


class InvoiceParser:
    """Service for parsing energy invoices from PDF using OCR."""

    _shared_invoices: dict = {}

    def __init__(self):
        # Shared in-memory storage across parser instances.
        self._invoices = self._shared_invoices

        # Common patterns for Australian energy invoices
        self._patterns = {
            "invoice_number": r"(?:Invoice(?:\s*No\.?|\s*Number)?|Tax Invoice)\s*[:#-]?\s*([A-Z0-9/-]*\d[A-Z0-9/-]*)",
            "invoice_date": r"(?:Issue Date|Invoice Date|Date Issued|Date)\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})",
            "due_date": r"(?:Due Date|Payment Due|Direct Debit date)\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})",
            "total": r"(?:Total(?: Due)?|Amount Due)[:\s]*\$?([\d,]+\.?\d*)",
            "gst": r"(?:GST|Goods and Services Tax)[:\s]*\$?([\d,]+\.?\d*)",
            "billing_period": r"(?:Bill(?:ing)?\s+period|Billing\s+Period|Period)\s*[:\-]?\s*(\d{1,2}(?:[/-]\d{1,2}[/-]\d{2,4}|\s+[A-Za-z]{3,9}\s+\d{4}))\s*(?:to|-)\s*(\d{1,2}(?:[/-]\d{1,2}[/-]\d{2,4}|\s+[A-Za-z]{3,9}\s+\d{4}))",
        }

    async def parse_invoice(self, file_id: str, pdf_content: bytes) -> dict:
        """Parse an invoice PDF and return structured fields plus confidence."""
        text = await self._extract_text_from_pdf(pdf_content)
        invoice_data = self._parse_invoice_text(text)
        confidence = self._calculate_confidence(invoice_data)

        warnings = []
        if confidence < 0.7:
            warnings.append("Low confidence extraction - please verify details")
        if not invoice_data.get("nmi"):
            warnings.append("NMI not found - please enter manually")

        self._invoices[file_id] = invoice_data

        return {
            "invoice": invoice_data,
            "confidence": confidence,
            "warnings": warnings,
        }

    async def _extract_text_from_pdf(self, pdf_content: bytes) -> str:
        """Extract invoice text via OCR first, then embedded-text fallback."""
        text = self._extract_embedded_text(pdf_content)
        if text.strip():
            return text

        text = self._extract_text_with_ocr(pdf_content)
        if text.strip():
            return text

        raise ValueError(
            "Unable to extract text from PDF. Ensure Tesseract/poppler are installed or use a text-based PDF."
        )

    def _extract_text_with_ocr(self, pdf_content: bytes) -> str:
        """OCR path using pdf2image + pytesseract when available."""
        try:
            from pdf2image import convert_from_bytes
            import pytesseract
        except Exception:
            return ""

        try:
            images = convert_from_bytes(pdf_content, dpi=300)
        except Exception:
            return ""

        chunks: list[str] = []
        for image in images:
            try:
                chunks.append(pytesseract.image_to_string(image))
            except Exception:
                continue

        return "\n".join(chunks)

    def _extract_embedded_text(self, pdf_content: bytes) -> str:
        """Fallback extraction path for text PDFs."""
        try:
            from pypdf import PdfReader
        except Exception:
            return ""

        try:
            reader = PdfReader(io.BytesIO(pdf_content))
        except Exception:
            return ""

        chunks = []
        for page in reader.pages:
            try:
                extracted = page.extract_text() or ""
                if extracted:
                    chunks.append(extracted)
            except Exception:
                continue

        return "\n".join(chunks)

    def _parse_invoice_text(self, text: str) -> dict:
        """Parse extracted invoice text into structured schema-compatible fields."""
        nmi_value = self._extract_nmi(text)
        invoice_number = self._extract_invoice_number(text)
        invoice_num_match = re.search(self._patterns["invoice_number"], text, re.IGNORECASE)
        invoice_date_match = re.search(self._patterns["invoice_date"], text, re.IGNORECASE)
        due_date_match = re.search(self._patterns["due_date"], text, re.IGNORECASE)
        billing_period_match = re.search(self._patterns["billing_period"], text, re.IGNORECASE)
        total_match = re.search(self._patterns["total"], text, re.IGNORECASE)
        gst_match = re.search(self._patterns["gst"], text, re.IGNORECASE)

        line_items = self._parse_line_items(text)
        service_address = self._extract_service_address(text)
        service_state, service_postcode = self._extract_state_postcode(service_address or text)

        subtotal = sum(item["amount"] for item in line_items if item["charge_type"] != "gst")
        gst = Decimal(gst_match.group(1).replace(",", "")) if gst_match else Decimal("0")
        total = Decimal(total_match.group(1).replace(",", "")) if total_match else (subtotal + gst)

        start = self._parse_date(billing_period_match.group(1)) if billing_period_match else date.today()
        end = self._parse_date(billing_period_match.group(2)) if billing_period_match else start

        return {
            "invoice_number": invoice_number or (invoice_num_match.group(1) if invoice_num_match else "Unknown"),
            "invoice_date": self._parse_date(invoice_date_match.group(1)) if invoice_date_match else date.today(),
            "due_date": self._parse_date(due_date_match.group(1)) if due_date_match else None,
            "retailer": self._detect_retailer(text),
            "energy_plan_name": self._extract_energy_plan_name(text),
            "network_provider": self._detect_network_provider(text),
            "service_address": service_address,
            "service_state": service_state,
            "service_postcode": service_postcode,
            "nmi": nmi_value or "UNKNOWN",
            "billing_period_start": start,
            "billing_period_end": end,
            "line_items": line_items,
            "subtotal": subtotal,
            "gst": gst,
            "total": total,
            "amount_due": total,
        }

    def _parse_line_items(self, text: str) -> list[dict]:
        """Parse line items with quantity/rate/amount patterns."""
        items = []

        seen = set()
        detailed_pattern = re.compile(
            r"(.+?):\s*(\d+(?:,\d+)?(?:\.\d+)?)\s*(kWh|days?)\s*@?\s*\$?([\d.]+)\s*(?:/|per\s*)?(?:kWh|day)?\s*=?\s*\$?([\d,]+\.?\d*)",
            re.IGNORECASE,
        )
        simple_amount_pattern = re.compile(r"(.+?)\s+\$([\d,]+\.?\d*)$", re.IGNORECASE)
        row_pattern_desc_first = re.compile(
            r"^(?P<description>.+?)\s+"
            r"(?P<tou>At all times|Daily|Peak|Off-peak|Off peak|Shoulder|Night)\s+"
            r"(?P<qty>[\d,]+(?:\.\d+)?)\s+"
            r"(?P<unit>kWh|days?)\s+"
            r"\$?(?P<rate>[\d.]+)\s+"
            r"\$?(?P<amount>[\d,]+(?:\.\d+)?)(?P<credit>cr)?$",
            re.IGNORECASE,
        )
        row_pattern_qty_first = re.compile(
            r"^(?P<qty>[\d,]+(?:\.\d+)?)\s+"
            r"(?P<unit>kWh|days?)\s+"
            r"\$?(?P<rate>[\d.]+)\s+"
            r"\$?(?P<amount>[\d,]+(?:\.\d+)?)(?P<credit>cr)?"
            r"(?P<trailing>.+)$",
            re.IGNORECASE,
        )
        trailing_tou_pattern = re.compile(
            r"^(?P<tou>At all times|Daily|Peak|Off-peak|Off peak|Shoulder|Night)\s*(?P<description>.+)$",
            re.IGNORECASE,
        )

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            # Skip summary/section lines. We only want individual charge lines.
            if re.search(
                r"^(Usage and supply charges|Solar export|Total charges|Total credits|Total new charges and credits|Bill period|Understand your bill|Direct Debit amount due|Amount due)\b",
                line,
                re.IGNORECASE,
            ):
                continue

            table_row = row_pattern_desc_first.search(line)
            if table_row:
                description = table_row.group("description").strip()
                key = description.lower()
                if key not in seen:
                    amount = self._parse_amount(table_row.group("amount"), is_credit=bool(table_row.group("credit")))
                    items.append(
                        {
                            "description": description,
                            "charge_type": self._classify_charge(description),
                            "quantity": float(table_row.group("qty").replace(",", "")),
                            "unit": "day" if "day" in table_row.group("unit").lower() else "kWh",
                            "rate": Decimal(table_row.group("rate")),
                            "amount": amount,
                            "tariff_code": self._extract_tariff_code(description),
                        }
                    )
                    seen.add(key)
                continue

            qty_first = row_pattern_qty_first.search(line)
            if qty_first:
                trailing = qty_first.group("trailing").strip()
                trailing_match = trailing_tou_pattern.search(trailing)
                if trailing_match:
                    description = trailing_match.group("description").strip()
                    if description:
                        key = description.lower()
                        if key not in seen:
                            amount = self._parse_amount(qty_first.group("amount"), is_credit=bool(qty_first.group("credit")))
                            items.append(
                                {
                                    "description": description,
                                    "charge_type": self._classify_charge(description),
                                    "quantity": float(qty_first.group("qty").replace(",", "")),
                                    "unit": "day" if "day" in qty_first.group("unit").lower() else "kWh",
                                    "rate": Decimal(qty_first.group("rate")),
                                    "amount": amount,
                                    "tariff_code": self._extract_tariff_code(description),
                                }
                            )
                            seen.add(key)
                        continue

            match = detailed_pattern.search(line)
            if match:
                description = match.group(1).strip()
                key = description.lower()
                if key in seen:
                    continue
                items.append(
                    {
                        "description": description,
                        "charge_type": self._classify_charge(description),
                        "quantity": float(match.group(2).replace(",", "")),
                        "unit": "day" if "day" in match.group(3).lower() else "kWh",
                        "rate": Decimal(match.group(4)),
                        "amount": Decimal(match.group(5).replace(",", "")),
                        "tariff_code": self._extract_tariff_code(description),
                    }
                )
                seen.add(key)
                continue

            fallback = simple_amount_pattern.search(line)
            if not fallback:
                continue

            description = fallback.group(1).strip()
            if self._classify_charge(description) == "usage" and "usage" not in description.lower():
                continue
            key = description.lower()
            if key in seen:
                continue

            items.append(
                {
                    "description": description,
                    "charge_type": self._classify_charge(description),
                    "quantity": None,
                    "unit": None,
                    "rate": None,
                    "amount": Decimal(fallback.group(2).replace(",", "")),
                    "tariff_code": self._extract_tariff_code(description),
                }
            )
            seen.add(key)

        return items

    @staticmethod
    def _parse_amount(raw_amount: str, is_credit: bool = False) -> Decimal:
        amount = Decimal(raw_amount.replace(",", ""))
        return -amount if is_credit else amount

    def _classify_charge(self, description: str) -> str:
        """Classify a charge type from line item description."""
        desc_lower = description.lower()

        if "supply" in desc_lower or "service" in desc_lower:
            return "supply"
        if "network" in desc_lower or "distribution" in desc_lower or "transmission" in desc_lower:
            return "network"
        if "demand" in desc_lower:
            return "demand"
        if "meter" in desc_lower:
            return "metering"
        if "green" in desc_lower or "environmental" in desc_lower or re.search(r"\brec\b", desc_lower):
            return "environmental"
        if "gst" in desc_lower:
            return "gst"
        return "usage"

    def _detect_retailer(self, text: str) -> str:
        """Detect retailer from invoice body."""
        retailers = [
            "AGL",
            "Origin Energy",
            "EnergyAustralia",
            "Red Energy",
            "Simply Energy",
            "Alinta Energy",
            "Powershop",
            "Momentum Energy",
        ]

        for retailer in retailers:
            if retailer.lower() in text.lower():
                return retailer

        return "Unknown Retailer"

    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse date string to date object."""
        if not date_str:
            return None

        formats = ["%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y", "%d %b %Y", "%d %B %Y"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue

        return None

    def _extract_nmi(self, text: str) -> Optional[str]:
        patterns = [
            r"National\s+Metering\s+Identifier\s*\(NMI\)\s*[:\-]?\s*([A-Z0-9 ]{10,20})",
            r"\bNMI\b\s*[:\-]?\s*([A-Z0-9 ]{10,20})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if not match:
                continue
            normalized = re.sub(r"[^A-Z0-9]", "", match.group(1).upper())
            if len(normalized) in (10, 11):
                return normalized
        return None

    def _extract_invoice_number(self, text: str) -> Optional[str]:
        match = re.search(self._patterns["invoice_number"], text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            if re.search(r"\d", value):
                return value

        # Fallback for invoices that print number on a standalone first line e.g. 037/99871.
        top_code = re.search(r"(?m)^\s*(\d{2,6}/\d{3,12})\s*$", text)
        if top_code:
            return top_code.group(1)

        return None

    def _extract_energy_plan_name(self, text: str) -> Optional[str]:
        match = re.search(r"Summary of your energy plan\s+([^\n]+)", text, re.IGNORECASE)
        if not match:
            return None
        value = match.group(1).strip()
        return value or None

    def _detect_network_provider(self, text: str) -> Optional[str]:
        providers = [
            "Energex",
            "Ergon Energy",
            "Ausgrid",
            "Endeavour Energy",
            "Essential Energy",
            "Evoenergy",
            "TasNetworks",
            "United Energy",
            "CitiPower",
            "Powercor",
            "Jemena",
            "AusNet",
        ]
        lowered = text.lower()
        for provider in providers:
            if provider.lower() in lowered:
                return provider
        return None

    def _extract_service_address(self, text: str) -> Optional[str]:
        label_patterns = [
            r"(?:Service|Supply|Site|Property)\s+address\s*[:\-]?\s*([^\n]+)",
            r"NMI\s+address\s*[:\-]?\s*([^\n]+)",
        ]
        for pattern in label_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if not match:
                continue
            candidate = self._normalize_address_text(match.group(1))
            if self._looks_like_au_address(candidate):
                return candidate

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for idx, line in enumerate(lines):
            if "nmi" not in line.lower():
                continue
            for offset in range(1, 4):
                if idx + offset >= len(lines):
                    break
                candidate = self._normalize_address_text(lines[idx + offset])
                if self._looks_like_au_address(candidate):
                    return candidate
        return None

    @staticmethod
    def _extract_state_postcode(text: str) -> tuple[Optional[str], Optional[str]]:
        if not text:
            return None, None
        match = re.search(r"\b(NSW|QLD|VIC|SA|WA|TAS|ACT|NT)\b[ ,]+(\d{4})\b", text, re.IGNORECASE)
        if not match:
            return None, None
        return match.group(1).upper(), match.group(2)

    @staticmethod
    def _normalize_address_text(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip(" ,.-")

    def _looks_like_au_address(self, text: str) -> bool:
        if not text:
            return False
        has_state_postcode = re.search(r"\b(NSW|QLD|VIC|SA|WA|TAS|ACT|NT)\b[ ,]+\d{4}\b", text, re.IGNORECASE)
        has_street_number = re.search(r"\b\d{1,5}\b", text)
        has_street_word = re.search(
            r"\b(st|street|rd|road|ave|avenue|dr|drive|ct|court|cres|crescent|pl|place|way|pde|parade)\b",
            text,
            re.IGNORECASE,
        )
        return bool(has_state_postcode and has_street_number and has_street_word)

    @staticmethod
    def _extract_tariff_code(description: str) -> Optional[str]:
        match = re.search(r"\bTariff\s*([A-Za-z0-9]+)\b", description, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        return None

    def _calculate_confidence(self, invoice_data: dict) -> float:
        """Calculate confidence score for parsed invoice fields."""
        required_fields = ["nmi", "invoice_number", "billing_period_start", "billing_period_end", "total"]
        found = 0
        for field in required_fields:
            value = invoice_data.get(field)
            if field == "nmi" and value == "UNKNOWN":
                continue
            if field == "invoice_number" and value == "Unknown":
                continue
            if value:
                found += 1

        confidence = found / len(required_fields)
        if invoice_data.get("line_items"):
            confidence = min(1.0, confidence + 0.05 * len(invoice_data["line_items"]))

        return round(confidence, 2)

    async def get_invoice(self, file_id: str) -> Optional[dict]:
        """Retrieve previously parsed invoice."""
        return self._invoices.get(file_id)
