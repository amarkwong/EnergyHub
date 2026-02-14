"""Authentication endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db, init_db
from app.models.auth import User
from app.schemas.auth import AuthTokenResponse, LoginRequest, RegisterRequest, UserOut
from app.services.auth_service import auth_service, get_current_user


router = APIRouter()


def _serialize_user(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        account_type=user.account_type,
        display_name=user.display_name,
        created_at=user.created_at,
    )


@router.post("/register", response_model=AuthTokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    init_db()
    try:
        user = auth_service.register_user(
            db=db,
            email=payload.email,
            password=payload.password,
            account_type=payload.account_type,
            display_name=payload.display_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    token, expires_at = auth_service.issue_session(db, user)
    return AuthTokenResponse(access_token=token, expires_at=expires_at, user=_serialize_user(user))


@router.post("/login", response_model=AuthTokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    init_db()
    user = auth_service.authenticate(db, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token, expires_at = auth_service.issue_session(db, user)
    return AuthTokenResponse(access_token=token, expires_at=expires_at, user=_serialize_user(user))


@router.post("/logout")
def logout(
    authorization: str = Header(..., alias="Authorization"),
    db: Session = Depends(get_db),
):
    token = authorization.split(" ", 1)[1] if " " in authorization else ""
    if token:
        auth_service.revoke_token(db, token)
    return {"status": "ok"}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return _serialize_user(user)

