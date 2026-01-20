"""Tests for NEM12 service."""
import pytest
from app.services.nem12_service import NEM12Service


@pytest.fixture
def nem12_service():
    return NEM12Service()


@pytest.fixture
def sample_nem12_content():
    return """100,NEM12,202401150000,ENERGYCO,RETAILER
200,1234567890,E1,E1,E1,N1,METSER01,kWh,30,
300,20240101,1.5,1.2,1.3,1.4,1.6,1.8,2.0,2.2,2.4,2.6,2.8,3.0,3.2,3.4,3.6,3.4,3.2,3.0,2.8,2.6,2.4,2.2,2.0,1.8,1.6,1.4,1.2,1.0,0.8,0.6,0.4,0.5,0.6,0.7,0.8,0.9,1.0,1.1,1.2,1.3,1.4,1.5,1.6,1.7,1.8,1.9,2.0,A,,,
900"""


@pytest.mark.asyncio
async def test_process_nem12_valid_file(nem12_service, sample_nem12_content):
    """Test processing a valid NEM12 file."""
    result = await nem12_service.process_nem12("test-file-1", sample_nem12_content)

    assert len(result) > 0
    assert result[0]['nmi'] == '1234567890'
    assert result[0]['unit_of_measure'] == 'kWh'
    assert result[0]['interval_length'] == 30


@pytest.mark.asyncio
async def test_process_nem12_empty_file(nem12_service):
    """Test processing an empty file."""
    result = await nem12_service.process_nem12("test-file-2", "")
    assert result == []


@pytest.mark.asyncio
async def test_get_consumption_summary(nem12_service, sample_nem12_content):
    """Test getting consumption summary."""
    file_id = "test-file-3"
    await nem12_service.process_nem12(file_id, sample_nem12_content)

    summaries = await nem12_service.get_consumption_summary(file_id)

    assert len(summaries) > 0
    assert 'total_kwh' in summaries[0]
    assert 'peak_kwh' in summaries[0]
    assert 'off_peak_kwh' in summaries[0]


@pytest.mark.asyncio
async def test_get_interval_data(nem12_service, sample_nem12_content):
    """Test getting interval data."""
    file_id = "test-file-4"
    await nem12_service.process_nem12(file_id, sample_nem12_content)

    intervals = await nem12_service.get_interval_data(file_id)

    assert len(intervals) > 0
    assert 'date' in intervals[0]
    assert 'interval' in intervals[0]
    assert 'value' in intervals[0]


@pytest.mark.asyncio
async def test_get_interval_data_not_found(nem12_service):
    """Test getting interval data for non-existent file."""
    intervals = await nem12_service.get_interval_data("nonexistent")
    assert intervals == []
