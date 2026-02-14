"""Tests for auth and account ownership module."""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.main import app


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_register_login_and_nmi_assignment_flow():
    client = TestClient(app)
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    password = "StrongPass123!"

    register = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": password,
            "account_type": "residential",
            "display_name": "Test User",
        },
    )
    assert register.status_code == 200
    token = register.json()["access_token"]

    me = client.get("/api/auth/me", headers=_auth_header(token))
    assert me.status_code == 200
    assert me.json()["email"] == email
    assert me.json()["account_type"] == "residential"

    add_nmi = client.post("/api/account/nmis", headers=_auth_header(token), json={"nmi": "31201328846", "label": "Home"})
    assert add_nmi.status_code == 200
    assert add_nmi.json()["nmi"] == "31201328846"

    assignment = client.post(
        "/api/account/nmi-plan-assignments",
        headers=_auth_header(token),
        json={
            "nmi": "31201328846",
            "effective_from": "2025-07-01",
            "effective_to": "2026-06-30",
            "retailer_name": "AGL",
            "network_tariff_code": "12E",
            "source_invoice_file_id": "inv-demo-1",
        },
    )
    assert assignment.status_code == 200
    assert assignment.json()["network_tariff_code"] == "12E"

    listed = client.get("/api/account/nmi-plan-assignments?nmi=31201328846", headers=_auth_header(token))
    assert listed.status_code == 200
    assert len(listed.json()) >= 1

    nmi_locations = client.get("/api/account/nmi-locations", headers=_auth_header(token))
    assert nmi_locations.status_code == 200
    assert len(nmi_locations.json()) >= 1
    assert nmi_locations.json()[0]["nmi"] == "31201328846"

    login = client.post("/api/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    assert login.json()["user"]["email"] == email
