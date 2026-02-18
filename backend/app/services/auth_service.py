"""Authentication and account ownership services."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.database import get_db
from app.models.auth import User, UserNmi, UserNmiPlanAssignment, UserSession
from app.models.energy_plan import EnergyPlan, Retailer
from app.schemas.invoice import ParsedInvoice
from app.services.geocoding_service import GeocodingService


class AuthService:
    def __init__(self):
        self._settings = get_settings()
        self._geocoding = GeocodingService()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def hash_password(password: str) -> str:
        salt = secrets.token_hex(16)
        rounds = 240_000
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), rounds)
        return f"pbkdf2_sha256${rounds}${salt}${digest.hex()}"

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        try:
            algo, rounds_str, salt, digest_hex = hashed.split("$", 3)
            if algo != "pbkdf2_sha256":
                return False
            rounds = int(rounds_str)
        except Exception:
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), rounds).hex()
        return secrets.compare_digest(digest, digest_hex)

    def register_user(self, db: Session, email: str, password: str, account_type: str, display_name: Optional[str]) -> User:
        existing = db.query(User).filter(func.lower(User.email) == email.lower()).first()
        if existing:
            raise ValueError("Email already registered")
        user = User(
            email=email.lower(),
            password_hash=self.hash_password(password),
            account_type=account_type,
            display_name=display_name,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def authenticate(self, db: Session, email: str, password: str) -> Optional[User]:
        user = db.query(User).filter(func.lower(User.email) == email.lower()).first()
        if not user:
            return None
        if not self.verify_password(password, user.password_hash):
            return None
        return user

    def issue_session(self, db: Session, user: User) -> tuple[str, datetime]:
        raw = secrets.token_urlsafe(40)
        expires_at = self._now() + timedelta(hours=self._settings.auth_session_ttl_hours)
        session = UserSession(user_id=user.id, token_hash=self._hash_token(raw), expires_at=expires_at)
        db.add(session)
        db.commit()
        return raw, expires_at

    def revoke_token(self, db: Session, token: str) -> None:
        token_hash = self._hash_token(token)
        session = db.query(UserSession).filter(UserSession.token_hash == token_hash, UserSession.revoked_at.is_(None)).first()
        if session:
            session.revoked_at = self._now()
            db.commit()

    def get_user_by_token(self, db: Session, token: str) -> Optional[User]:
        token_hash = self._hash_token(token)
        session = (
            db.query(UserSession)
            .filter(
                UserSession.token_hash == token_hash,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > self._now(),
            )
            .first()
        )
        if not session:
            return None
        return db.query(User).filter(User.id == session.user_id).first()

    def get_or_create_user_nmi(self, db: Session, user_id: int, nmi: str, label: Optional[str] = None) -> UserNmi:
        normalized = nmi.strip().upper()
        user_nmi = db.query(UserNmi).filter(UserNmi.user_id == user_id, UserNmi.nmi == normalized).first()
        if user_nmi:
            if label and user_nmi.label != label:
                user_nmi.label = label
                db.commit()
                db.refresh(user_nmi)
            return user_nmi
        user_nmi = UserNmi(user_id=user_id, nmi=normalized, label=label)
        db.add(user_nmi)
        db.commit()
        db.refresh(user_nmi)
        return user_nmi

    def add_plan_assignment(
        self,
        db: Session,
        user_id: int,
        nmi: str,
        effective_from,
        effective_to,
        retailer_name: Optional[str],
        retail_plan_id: Optional[int],
        network_tariff_code: Optional[str],
        source_invoice_file_id: Optional[str],
    ) -> UserNmiPlanAssignment:
        user_nmi = self.get_or_create_user_nmi(db, user_id=user_id, nmi=nmi)
        assignment = UserNmiPlanAssignment(
            user_nmi_id=user_nmi.id,
            effective_from=effective_from,
            effective_to=effective_to,
            retailer_name=retailer_name,
            retail_plan_id=retail_plan_id,
            network_tariff_code=network_tariff_code,
            source_invoice_file_id=source_invoice_file_id,
        )
        db.add(assignment)
        db.commit()
        db.refresh(assignment)
        return assignment

    def apply_invoice_relationships(self, db: Session, user: User, invoice_file_id: str, parsed_invoice: ParsedInvoice | dict) -> None:
        payload = parsed_invoice if isinstance(parsed_invoice, dict) else parsed_invoice.model_dump()
        nmi = (payload.get("nmi") or "").strip().upper()
        if not nmi or nmi == "UNKNOWN":
            return

        user_nmi = self.get_or_create_user_nmi(db, user_id=user.id, nmi=nmi)
        self._apply_service_address(db=db, user_nmi=user_nmi, payload=payload)
        retailer_name = payload.get("retailer")
        period_start = payload.get("billing_period_start")
        period_end = payload.get("billing_period_end")

        plan_id = None
        if retailer_name and retailer_name != "Unknown Retailer":
            plan_id = self._resolve_plan_id(db, retailer_name=retailer_name, effective_date=period_start)

        network_tariff_code = None
        for item in payload.get("line_items", []):
            code = item.get("tariff_code")
            if code:
                network_tariff_code = code
                break

        # Upsert: update existing assignment or create new one
        existing = (
            db.query(UserNmiPlanAssignment)
            .filter(
                UserNmiPlanAssignment.user_nmi_id == user_nmi.id,
                UserNmiPlanAssignment.effective_from == period_start,
                UserNmiPlanAssignment.effective_to == period_end,
            )
            .first()
        )
        if existing:
            existing.retailer_name = retailer_name
            existing.retail_plan_id = plan_id
            if network_tariff_code is not None:
                existing.network_tariff_code = network_tariff_code
            existing.source_invoice_file_id = invoice_file_id
        else:
            assignment = UserNmiPlanAssignment(
                user_nmi_id=user_nmi.id,
                effective_from=period_start,
                effective_to=period_end,
                retailer_name=retailer_name,
                retail_plan_id=plan_id,
                network_tariff_code=network_tariff_code,
                source_invoice_file_id=invoice_file_id,
            )
            db.add(assignment)
        db.commit()

    def _apply_service_address(self, db: Session, user_nmi: UserNmi, payload: dict) -> None:
        raw_address = (payload.get("service_address") or "").strip()
        service_state = (payload.get("service_state") or user_nmi.state or "").strip().upper() or None
        service_postcode = (payload.get("service_postcode") or user_nmi.postcode or "").strip() or None

        # Always persist state/postcode when available, even without a full address.
        if service_state:
            user_nmi.state = service_state
        if service_postcode:
            user_nmi.postcode = service_postcode

        if not raw_address:
            # Fall back to state centroid if we at least have a state.
            if service_state and not user_nmi.latitude:
                geocode = self._geocoding.geocode_au_address("", state=service_state)
                if geocode.latitude is not None:
                    user_nmi.latitude = geocode.latitude
                    user_nmi.longitude = geocode.longitude
                    user_nmi.geocode_source = geocode.source
                    user_nmi.geocoded_at = geocode.geocoded_at
            db.add(user_nmi)
            return

        geocode = self._geocoding.geocode_au_address(raw_address, state=service_state)
        user_nmi.service_address = raw_address
        if geocode.latitude is not None and geocode.longitude is not None:
            user_nmi.latitude = geocode.latitude
            user_nmi.longitude = geocode.longitude
            user_nmi.geocode_source = geocode.source
            user_nmi.geocoded_at = geocode.geocoded_at
        db.add(user_nmi)

    @staticmethod
    def _resolve_plan_id(db: Session, retailer_name: str, effective_date) -> Optional[int]:
        if not effective_date:
            return None
        retailer = db.query(Retailer).filter(func.lower(Retailer.name) == retailer_name.lower()).first()
        if not retailer:
            return None
        plan = (
            db.query(EnergyPlan)
            .filter(
                EnergyPlan.retailer_id == retailer.id,
                EnergyPlan.effective_from <= effective_date,
                (EnergyPlan.effective_to.is_(None) | (EnergyPlan.effective_to >= effective_date)),
            )
            .order_by(EnergyPlan.effective_from.desc())
            .first()
        )
        return plan.id if plan else None


auth_service = AuthService()


def _extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def get_current_user(
    authorization: str = Header(..., alias="Authorization"),
    db: Session = Depends(get_db),
) -> User:
    token = _extract_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    user = auth_service.get_user_by_token(db, token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


def get_optional_current_user(
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> Optional[User]:
    token = _extract_bearer_token(authorization)
    if not token:
        return None
    return auth_service.get_user_by_token(db, token)
