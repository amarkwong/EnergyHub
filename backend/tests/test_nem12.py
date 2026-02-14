"""Tests for NEM12 service."""
from pathlib import Path

import pytest

from app.services.nem12_service import NEM12Service


FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def nem12_service():
    return NEM12Service()


def _read_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fixture_name", "expected_nmi", "expected_interval_length", "expected_intervals"),
    [
        ("nem12_5m.csv", "5000000001", 5, 288),
        ("nem12_15m.csv", "5000000002", 15, 96),
        ("nem12_30m.csv", "5000000003", 30, 48),
    ],
)
async def test_process_nem12_interval_variants(
    nem12_service,
    fixture_name,
    expected_nmi,
    expected_interval_length,
    expected_intervals,
):
    """Parses 5/15/30-minute files with correct interval counts."""
    file_id = f"test-{fixture_name}"
    content = _read_fixture(fixture_name)
    result = await nem12_service.process_nem12(file_id, content)

    assert len(result) == 1
    meter = result[0]
    assert meter["nmi"] == expected_nmi
    assert meter["interval_length"] == expected_interval_length
    assert meter["interval_count"] == expected_intervals

    intervals = await nem12_service.get_interval_data(file_id)
    assert len(intervals) == expected_intervals
    assert intervals[0]["interval"] == 1
    assert intervals[-1]["interval"] == expected_intervals


@pytest.mark.asyncio
async def test_get_consumption_summary_balances_peak_and_offpeak(nem12_service):
    """Summary split should add up to total usage."""
    file_id = "test-summary-30m"
    await nem12_service.process_nem12(file_id, _read_fixture("nem12_30m.csv"))

    summaries = await nem12_service.get_consumption_summary(file_id)
    assert len(summaries) == 1

    summary = summaries[0]
    assert summary["period_start"].isoformat() == "2026-01-01"
    assert summary["period_end"].isoformat() == "2026-01-01"
    assert pytest.approx(summary["peak_kwh"] + summary["off_peak_kwh"], 1e-9) == summary["total_kwh"]


@pytest.mark.asyncio
async def test_get_interval_data_sorted_by_date_then_interval(nem12_service):
    """Interval query should return stable ordering even if file rows are unsorted."""
    # 30-minute meter; only first few interval values are populated on each date.
    content = """100,NEM12,202602090000,ENERGYHUB,TEST
200,5555555555,E1,E1,E1,N1,MTRSORT01,kWh,30,
300,20260102,1.0,2.0,3.0,A,,,
300,20260101,4.0,5.0,6.0,A,,,
900"""
    file_id = "test-sorted-intervals"
    await nem12_service.process_nem12(file_id, content)

    intervals = await nem12_service.get_interval_data(file_id)
    assert len(intervals) == 6
    assert [i["date"] for i in intervals[:3]] == ["2026-01-01", "2026-01-01", "2026-01-01"]
    assert [i["date"] for i in intervals[3:]] == ["2026-01-02", "2026-01-02", "2026-01-02"]
    assert [i["interval"] for i in intervals] == [1, 2, 3, 1, 2, 3]


@pytest.mark.asyncio
async def test_process_nem12_malformed_rows_tolerated(nem12_service):
    """Invalid numeric/date values should be skipped without crashing parser."""
    content = """100,NEM12,202602090000,ENERGYHUB,TEST
200,6666666666,E1,E1,E1,N1,MTRBAD01,kWh,30,
300,notadate,1.0,2.0,3.0,A,,,
300,20260101,1.0,ABC,2.0,A,,,
900"""
    result = await nem12_service.process_nem12("test-malformed", content)
    assert len(result) == 1
    meter = result[0]
    # Only valid values from the valid-date row are counted.
    assert meter["interval_count"] == 2
    assert meter["total_consumption"] == pytest.approx(3.0)


@pytest.mark.asyncio
async def test_process_nem12_empty_file(nem12_service):
    """Test processing an empty file."""
    result = await nem12_service.process_nem12("test-file-empty", "")
    assert result == []


@pytest.mark.asyncio
async def test_get_interval_data_not_found(nem12_service):
    """Test getting interval data for non-existent file."""
    intervals = await nem12_service.get_interval_data("nonexistent")
    assert intervals == []
