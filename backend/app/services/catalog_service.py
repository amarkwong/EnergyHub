"""Singleton service that loads catalog.json and provides instant lookups.

Auto-reloads when the file's mtime changes (picks up nightly rebuild
without server restart).
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG_PATH = ROOT / "data" / "catalog.json"


class CatalogService:
    """In-memory catalog with auto-reload on file change."""

    def __init__(self, catalog_path: Path = DEFAULT_CATALOG_PATH):
        self._path = catalog_path
        self._lock = threading.Lock()
        self._mtime: float = 0.0
        self._metadata: dict[str, Any] = {}
        self._retailers: list[dict[str, Any]] = []
        self._plans: list[dict[str, Any]] = []
        self._postcode_index: dict[str, list[int]] = {}
        self._retailer_by_slug: dict[str, dict[str, Any]] = {}

    def _maybe_reload(self) -> None:
        """Reload catalog if the file has been modified."""
        if not self._path.exists():
            return
        mtime = self._path.stat().st_mtime
        if mtime == self._mtime:
            return
        with self._lock:
            # Double-check after acquiring lock
            mtime = self._path.stat().st_mtime
            if mtime == self._mtime:
                return
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            self._metadata = raw.get("metadata", {})
            self._retailers = raw.get("retailers", [])
            self._plans = raw.get("plans", [])
            self._postcode_index = raw.get("postcode_index", {})
            self._retailer_by_slug = {r["slug"]: r for r in self._retailers}
            self._mtime = mtime

    def get_metadata(self) -> dict[str, Any]:
        self._maybe_reload()
        return dict(self._metadata)

    def get_retailers(self) -> list[dict[str, Any]]:
        self._maybe_reload()
        return list(self._retailers)

    def get_plans_for_postcode(self, postcode: str) -> list[dict[str, Any]]:
        self._maybe_reload()
        indices = self._postcode_index.get(postcode, [])
        return [self._plans[i] for i in indices if i < len(self._plans)]

    def get_plans_for_retailer(self, slug: str) -> list[dict[str, Any]]:
        self._maybe_reload()
        return [p for p in self._plans if p.get("retailer_slug") == slug]

    def get_all_plans(self) -> list[dict[str, Any]]:
        self._maybe_reload()
        return list(self._plans)

    def get_plan_by_idx(self, idx: int) -> Optional[dict[str, Any]]:
        self._maybe_reload()
        if 0 <= idx < len(self._plans):
            return dict(self._plans[idx])
        return None

    def get_retailer(self, slug: str) -> Optional[dict[str, Any]]:
        self._maybe_reload()
        return self._retailer_by_slug.get(slug)


# Module-level singleton
_catalog = CatalogService()


def get_catalog() -> CatalogService:
    return _catalog
