"""Tests for energy plan ingestion and TOU alignment module."""
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_refresh_energy_plan_catalog_and_list_data():
    refresh = client.post("/api/energy-plans/refresh")
    assert refresh.status_code == 200
    payload = refresh.json()
    assert payload["retailers"] >= 1
    assert payload["plans"] >= 1
    assert payload["tou_definitions"] >= 1

    retailers = client.get("/api/energy-plans/retailers")
    assert retailers.status_code == 200
    slugs = [r["slug"] for r in retailers.json()]
    assert len(slugs) >= 1

    plans = client.get("/api/energy-plans/plans", params={"retailer_slug": slugs[0]})
    assert plans.status_code == 200
    assert len(plans.json()) > 0


def test_tou_alignment_for_network_definition():
    refresh = client.post("/api/energy-plans/refresh")
    assert refresh.status_code == 200

    resp = client.post(
        "/api/tou/align",
        json={
            "scope_type": "network",
            "scope_key": "ausgrid",
            "effective_date": "2026-01-10",
            "intervals": [
                {"interval_date": "2026-01-05", "interval_number": 29, "interval_length_minutes": 30, "value": 1.5},
                {"interval_date": "2026-01-05", "interval_number": 5, "interval_length_minutes": 30, "value": 0.7},
            ],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["aligned_count"] == 2
    names = {item["period_name"] for item in data["intervals"]}
    assert "peak" in names
    assert "off_peak" in names


def test_fetch_eme_endpoint_returns_schedule_and_persist_stats():
    fake_eme_payload = {
        "plans": [
            {
                "retailer": "AGL",
                "retailer_slug": "agl",
                "plan_id": "AGL123",
                "plan_name": "Sample Plan",
                "fuel_type": "ELECTRICITY",
                "customer_type": "RESIDENTIAL",
                "effective_from": "2026-01-01",
                "daily_supply_charge_cents": 100.0,
                "usage_rate_cents_per_kwh": 30.0,
                "tariff_type": "flat",
                "source_url": "https://example.com/plan",
            }
        ],
        "stats": {"agl": {"pages_fetched": 1, "detail_calls": 1, "plans_normalized": 1}},
    }

    with patch("app.api.energy_plans.eme_fetch_service.fetch_to_file", return_value=fake_eme_payload):
        with patch(
            "app.api.energy_plans.eme_fetch_service.persist_retail_catalog",
            return_value={"plans_total": 1, "plans_written": 1, "plans_skipped_missing_fields": 0},
        ):
            resp = client.post(
                "/api/energy-plans/fetch-eme",
                json={
                    "retailers": ["agl"],
                    "page_size": 10,
                    "max_plans_per_retailer": 5,
                    "fuel_type": "ELECTRICITY",
                    "persist_to_retail_catalog": True,
                    "refresh_db_after_persist": False,
                },
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["plans_fetched"] == 1
    assert data["retailers_requested"] == 1
    assert data["retail_catalog_persisted"] is True
    assert data["recommended_eventbridge_cron"] == "cron(0 2 1 1,7 ? *)"


def test_fetch_eme_all_retailers_from_dropdown_html():
    html = """
    <ul>
      <li><span>None/Not sure/Not in this list</span></li>
      <li><span>AGL</span></li>
      <li><span>Origin Energy</span></li>
    </ul>
    """
    fake_eme_payload = {
        "metadata": {"retailers_discovered": 2},
        "plans": [
            {
                "retailer": "AGL",
                "retailer_slug": "agl",
                "plan_id": "AGL123",
                "plan_name": "Sample Plan",
                "fuel_type": "ELECTRICITY",
                "customer_type": "RESIDENTIAL",
                "effective_from": "2026-01-01",
                "daily_supply_charge_cents": 100.0,
                "usage_rate_cents_per_kwh": 30.0,
                "tariff_type": "flat",
                "source_url": "https://example.com/plan",
            }
        ],
        "stats": {"agl": {"pages_fetched": 1, "detail_calls": 1, "plans_normalized": 1}},
        "resolved_retailers": [{"retailer_name": "AGL", "retailer_slug": "agl"}],
        "unresolved_retailers": [{"retailer_name": "Origin Energy", "slug_candidates": ["origin"], "errors": []}],
    }
    with patch("app.api.energy_plans.eme_fetch_service.fetch_from_dropdown_html", return_value=fake_eme_payload):
        with patch(
            "app.api.energy_plans.eme_fetch_service.persist_retail_catalog",
            return_value={"plans_total": 1, "plans_written": 1, "plans_skipped_missing_fields": 0},
        ):
            resp = client.post(
                "/api/energy-plans/fetch-eme-all-retailers",
                json={
                    "dropdown_html": html,
                    "persist_to_retail_catalog": True,
                    "refresh_db_after_persist": False,
                },
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["retailers_discovered"] == 2
    assert data["retailers_resolved"] == 1
    assert data["retailers_unresolved"] == 1
    assert data["recommended_eventbridge_cron"] == "cron(0 2 1 1,7 ? *)"
