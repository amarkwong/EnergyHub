"""Tariff data fetching service for Australian network providers."""
from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional
import json

from app.schemas.tariff import NetworkProvider, TariffType


class TariffFetcher:
    """
    Service for fetching tariff data from network providers.

    In production, this would scrape/fetch from provider websites or APIs.
    For now, it provides sample tariff structures.
    """

    def __init__(self):
        # Cache for tariff data
        self._cache = {}
        self._cache_expiry = {}

        # Sample tariff data for each provider
        # In production, these would be fetched from provider APIs/websites
        self._sample_tariffs = self._init_sample_tariffs()

    def _init_sample_tariffs(self) -> dict:
        """Initialize sample tariff data for Australian network providers."""
        return {
            NetworkProvider.AUSGRID: [
                {
                    'tariff_code': 'EA010',
                    'tariff_name': 'Residential Time of Use',
                    'network_provider': 'ausgrid',
                    'tariff_type': 'tou',
                    'effective_from': '2024-07-01',
                    'daily_supply_charge_cents': Decimal('98.37'),
                    'time_periods': [
                        {'name': 'peak', 'start_time': '14:00', 'end_time': '20:00',
                         'days': [0, 1, 2, 3, 4], 'rate_cents_per_kwh': Decimal('35.64')},
                        {'name': 'shoulder', 'start_time': '07:00', 'end_time': '14:00',
                         'days': [0, 1, 2, 3, 4], 'rate_cents_per_kwh': Decimal('12.87')},
                        {'name': 'shoulder', 'start_time': '20:00', 'end_time': '22:00',
                         'days': [0, 1, 2, 3, 4], 'rate_cents_per_kwh': Decimal('12.87')},
                        {'name': 'off_peak', 'start_time': '22:00', 'end_time': '07:00',
                         'days': [0, 1, 2, 3, 4, 5, 6], 'rate_cents_per_kwh': Decimal('8.14')},
                        {'name': 'off_peak', 'start_time': '00:00', 'end_time': '24:00',
                         'days': [5, 6], 'rate_cents_per_kwh': Decimal('8.14')},
                    ]
                },
                {
                    'tariff_code': 'EA025',
                    'tariff_name': 'Residential Flat Rate',
                    'network_provider': 'ausgrid',
                    'tariff_type': 'flat',
                    'effective_from': '2024-07-01',
                    'daily_supply_charge_cents': Decimal('98.37'),
                    'usage_rate_cents_per_kwh': Decimal('18.45'),
                }
            ],
            NetworkProvider.ENDEAVOUR_ENERGY: [
                {
                    'tariff_code': 'N70',
                    'tariff_name': 'Residential Time of Use',
                    'network_provider': 'endeavour_energy',
                    'tariff_type': 'tou',
                    'effective_from': '2024-07-01',
                    'daily_supply_charge_cents': Decimal('89.50'),
                    'time_periods': [
                        {'name': 'peak', 'start_time': '13:00', 'end_time': '20:00',
                         'days': [0, 1, 2, 3, 4], 'rate_cents_per_kwh': Decimal('29.82')},
                        {'name': 'shoulder', 'start_time': '07:00', 'end_time': '13:00',
                         'days': [0, 1, 2, 3, 4], 'rate_cents_per_kwh': Decimal('11.43')},
                        {'name': 'off_peak', 'start_time': '20:00', 'end_time': '07:00',
                         'days': [0, 1, 2, 3, 4, 5, 6], 'rate_cents_per_kwh': Decimal('7.89')},
                    ]
                }
            ],
            NetworkProvider.ESSENTIAL_ENERGY: [
                {
                    'tariff_code': 'BLNN2AU',
                    'tariff_name': 'Residential Single Rate',
                    'network_provider': 'essential_energy',
                    'tariff_type': 'flat',
                    'effective_from': '2024-07-01',
                    'daily_supply_charge_cents': Decimal('115.20'),
                    'usage_rate_cents_per_kwh': Decimal('14.85'),
                }
            ],
            NetworkProvider.AUSNET_SERVICES: [
                {
                    'tariff_code': 'NAST11',
                    'tariff_name': 'Small Residential TOU Weekday',
                    'network_provider': 'ausnet_services',
                    'tariff_type': 'tou',
                    'effective_from': '2024-01-01',
                    'daily_supply_charge_cents': Decimal('41.60'),
                    'time_periods': [
                        {'name': 'peak', 'start_time': '15:00', 'end_time': '21:00',
                         'days': [0, 1, 2, 3, 4], 'rate_cents_per_kwh': Decimal('18.14')},
                        {'name': 'off_peak', 'start_time': '00:00', 'end_time': '15:00',
                         'days': [0, 1, 2, 3, 4, 5, 6], 'rate_cents_per_kwh': Decimal('6.83')},
                        {'name': 'off_peak', 'start_time': '21:00', 'end_time': '24:00',
                         'days': [0, 1, 2, 3, 4, 5, 6], 'rate_cents_per_kwh': Decimal('6.83')},
                    ]
                }
            ],
            NetworkProvider.CITIPOWER: [
                {
                    'tariff_code': 'C1R',
                    'tariff_name': 'Residential Single Rate',
                    'network_provider': 'citipower',
                    'tariff_type': 'flat',
                    'effective_from': '2024-01-01',
                    'daily_supply_charge_cents': Decimal('31.90'),
                    'usage_rate_cents_per_kwh': Decimal('8.75'),
                }
            ],
            NetworkProvider.POWERCOR: [
                {
                    'tariff_code': 'D1',
                    'tariff_name': 'Residential Single Rate',
                    'network_provider': 'powercor',
                    'tariff_type': 'flat',
                    'effective_from': '2024-01-01',
                    'daily_supply_charge_cents': Decimal('55.20'),
                    'usage_rate_cents_per_kwh': Decimal('9.85'),
                }
            ],
            NetworkProvider.JEMENA: [
                {
                    'tariff_code': 'A100',
                    'tariff_name': 'Residential Anytime',
                    'network_provider': 'jemena',
                    'tariff_type': 'flat',
                    'effective_from': '2024-01-01',
                    'daily_supply_charge_cents': Decimal('36.70'),
                    'usage_rate_cents_per_kwh': Decimal('8.25'),
                }
            ],
            NetworkProvider.UNITED_ENERGY: [
                {
                    'tariff_code': 'LVS1R',
                    'tariff_name': 'Residential Single Rate',
                    'network_provider': 'united_energy',
                    'tariff_type': 'flat',
                    'effective_from': '2024-01-01',
                    'daily_supply_charge_cents': Decimal('34.50'),
                    'usage_rate_cents_per_kwh': Decimal('8.45'),
                }
            ],
            NetworkProvider.ENERGEX: [
                {
                    'tariff_code': '8400',
                    'tariff_name': 'Residential Flat',
                    'network_provider': 'energex',
                    'tariff_type': 'flat',
                    'effective_from': '2024-07-01',
                    'daily_supply_charge_cents': Decimal('55.80'),
                    'usage_rate_cents_per_kwh': Decimal('11.23'),
                }
            ],
            NetworkProvider.ERGON_ENERGY: [
                {
                    'tariff_code': '8400',
                    'tariff_name': 'Residential Flat',
                    'network_provider': 'ergon_energy',
                    'tariff_type': 'flat',
                    'effective_from': '2024-07-01',
                    'daily_supply_charge_cents': Decimal('102.50'),
                    'usage_rate_cents_per_kwh': Decimal('12.45'),
                }
            ],
            NetworkProvider.EVOENERGY: [
                {
                    'tariff_code': 'RES-TOU',
                    'tariff_name': 'Residential Time of Use',
                    'network_provider': 'evoenergy',
                    'tariff_type': 'tou',
                    'effective_from': '2024-07-01',
                    'daily_supply_charge_cents': Decimal('52.30'),
                    'time_periods': [
                        {'name': 'peak', 'start_time': '17:00', 'end_time': '20:00',
                         'days': [0, 1, 2, 3, 4], 'rate_cents_per_kwh': Decimal('24.50')},
                        {'name': 'off_peak', 'start_time': '00:00', 'end_time': '17:00',
                         'days': [0, 1, 2, 3, 4, 5, 6], 'rate_cents_per_kwh': Decimal('8.90')},
                        {'name': 'off_peak', 'start_time': '20:00', 'end_time': '24:00',
                         'days': [0, 1, 2, 3, 4, 5, 6], 'rate_cents_per_kwh': Decimal('8.90')},
                    ]
                }
            ],
            NetworkProvider.TASNETWORKS: [
                {
                    'tariff_code': 'TAS31',
                    'tariff_name': 'Residential Light and Power',
                    'network_provider': 'tasnetworks',
                    'tariff_type': 'flat',
                    'effective_from': '2024-07-01',
                    'daily_supply_charge_cents': Decimal('42.50'),
                    'usage_rate_cents_per_kwh': Decimal('12.80'),
                }
            ],
        }

    async def get_network_tariffs(
        self,
        provider: NetworkProvider,
        tariff_type: Optional[TariffType] = None,
        effective_date: Optional[date] = None
    ) -> list[dict]:
        """Get network tariffs for a provider."""
        tariffs = self._sample_tariffs.get(provider, [])

        if tariff_type:
            tariffs = [t for t in tariffs if t.get('tariff_type') == tariff_type.value]

        # Convert to proper format
        result = []
        for t in tariffs:
            tariff_data = {
                'tariff_code': t['tariff_code'],
                'tariff_name': t['tariff_name'],
                'network_provider': provider.value,
                'tariff_type': t['tariff_type'],
                'effective_from': t['effective_from'],
                'effective_to': None,
                'daily_supply_charge_cents': float(t['daily_supply_charge_cents']),
            }

            if t.get('usage_rate_cents_per_kwh'):
                tariff_data['usage_rate_cents_per_kwh'] = float(t['usage_rate_cents_per_kwh'])

            if t.get('time_periods'):
                tariff_data['time_periods'] = t['time_periods']

            result.append(tariff_data)

        return result

    async def get_tariff_by_code(
        self,
        provider: Optional[NetworkProvider],
        tariff_code: str
    ) -> Optional[dict]:
        """Get a specific tariff by code."""
        # Search all providers if not specified
        providers = [provider] if provider else list(NetworkProvider)

        for p in providers:
            tariffs = self._sample_tariffs.get(p, [])
            for t in tariffs:
                if t['tariff_code'] == tariff_code:
                    return {
                        'network_tariff': {
                            'tariff_code': t['tariff_code'],
                            'tariff_name': t['tariff_name'],
                            'network_provider': p.value,
                            'tariff_type': t['tariff_type'],
                            'effective_from': t['effective_from'],
                            'daily_supply_charge_cents': float(t['daily_supply_charge_cents']),
                            'usage_rate_cents_per_kwh': float(t.get('usage_rate_cents_per_kwh', 0)),
                            'time_periods': t.get('time_periods', []),
                        },
                        'last_updated': date.today().isoformat(),
                        'source_url': f'https://{p.value.replace("_", "")}.com.au/tariffs'
                    }

        return None

    async def refresh_provider_tariffs(self, provider: NetworkProvider) -> None:
        """
        Refresh tariff data from provider.

        In production, this would scrape the provider's website or call their API.
        """
        # Clear cache for this provider
        if provider in self._cache:
            del self._cache[provider]

        # In production: fetch fresh data from provider website/API
        # For now, just log that we would refresh
        print(f"Would refresh tariffs for {provider.value}")
