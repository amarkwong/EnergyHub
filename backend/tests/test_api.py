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


def test_upload_retailer_interval_csv_and_fetch_intervals(client):
    """Ingest retailer interval CSV format and query saved intervals by file_id."""
    content = """AccountNumber,NMI,DeviceNumber,DeviceType,RegisterCode,RateTypeDescription,StartDate,EndDate,ProfileReadValue,RegisterReadValue,QualityFlag
7086063356,31201328846,EDA72010309,COMMS4D,10309#E1,Generalusage,12/03/2025 12:00:00 AM,12/03/2025 12:29:59 AM,0.133,0,A
7086063356,31201328846,EDA72010309,COMMS4D,10309#E1,Generalusage,12/03/2025 12:30:00 AM,12/03/2025 12:59:59 AM,0.083,0,A
"""
    upload = client.post(
        "/api/nem12/upload-retailer-csv",
        files={"file": ("retailer_intervals.csv", content.encode("utf-8"), "text/csv")},
    )
    assert upload.status_code == 200
    payload = upload.json()
    assert payload["rows_inserted"] == 2
    assert payload["nmi_count"] == 1

    file_id = payload["file_id"]
    intervals = client.get(f"/api/nem12/{file_id}/intervals?nmi=31201328846")
    assert intervals.status_code == 200
    rows = intervals.json()
    assert len(rows) == 2
    assert rows[0]["register_code"] == "10309#E1"
    assert rows[0]["rate_type_description"] == "Generalusage"
    assert rows[0]["interval"] == 1
