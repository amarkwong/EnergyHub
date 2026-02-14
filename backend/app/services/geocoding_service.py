"""Address geocoding helpers for Australian NMI locations."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


AU_STATE_CENTROIDS = {
    "NSW": (-33.8688, 151.2093),
    "QLD": (-27.4698, 153.0251),
    "VIC": (-37.8136, 144.9631),
    "SA": (-34.9285, 138.6007),
    "WA": (-31.9505, 115.8605),
    "TAS": (-42.8821, 147.3272),
    "ACT": (-35.2809, 149.1300),
    "NT": (-12.4634, 130.8456),
}


@dataclass
class GeocodeResult:
    latitude: Optional[float]
    longitude: Optional[float]
    source: str
    geocoded_at: datetime


class GeocodingService:
    """Geocode Australian addresses with external lookup and local fallback."""

    _endpoint = "https://nominatim.openstreetmap.org/search"

    def geocode_au_address(self, address: str, state: Optional[str] = None) -> GeocodeResult:
        now = datetime.now(timezone.utc)
        normalized = (address or "").strip()
        if not normalized:
            return GeocodeResult(None, None, "none", now)

        query = normalized if "australia" in normalized.lower() else f"{normalized}, Australia"
        remote = self._lookup_nominatim(query)
        if remote is not None:
            lat, lng = remote
            return GeocodeResult(lat, lng, "nominatim", now)

        if state:
            centroid = AU_STATE_CENTROIDS.get(state.upper())
            if centroid:
                return GeocodeResult(centroid[0], centroid[1], "state_centroid", now)

        return GeocodeResult(None, None, "none", now)

    def _lookup_nominatim(self, query: str) -> Optional[tuple[float, float]]:
        params = urllib.parse.urlencode(
            {
                "q": query,
                "format": "jsonv2",
                "limit": "1",
                "countrycodes": "au",
                "addressdetails": "0",
            }
        )
        url = f"{self._endpoint}?{params}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "EnergyHub/0.1 (energy-nmi-map)",
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return None

        if not payload:
            return None
        first = payload[0]
        try:
            return float(first["lat"]), float(first["lon"])
        except Exception:
            return None
