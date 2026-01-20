"""Tests for API endpoints."""
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_list_network_providers(client):
    """Test listing network providers."""
    response = client.get("/api/tariffs/network-providers")
    assert response.status_code == 200

    providers = response.json()
    assert len(providers) > 0

    # Check for expected providers
    codes = [p["code"] for p in providers]
    assert "ausgrid" in codes
    assert "energex" in codes


def test_get_network_tariffs(client):
    """Test getting tariffs for a provider."""
    response = client.get("/api/tariffs/network/ausgrid")
    assert response.status_code == 200

    tariffs = response.json()
    assert len(tariffs) > 0
    assert "tariff_code" in tariffs[0]


def test_upload_invalid_file_type(client):
    """Test uploading invalid file type."""
    response = client.post(
        "/api/nem12/upload",
        files={"file": ("test.xyz", b"invalid content", "application/octet-stream")}
    )
    assert response.status_code == 400
