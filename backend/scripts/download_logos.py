"""Download provider logos into frontend/public/logos from logo_sources.json."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "app" / "data" / "logo_sources.json"
DEST_ROOT = ROOT.parent / "frontend" / "public" / "logos"


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")


def _ext_from_url(url: str) -> str:
    path = urlparse(url).path.lower()
    if path.endswith(".svg"):
        return ".svg"
    if path.endswith(".png"):
        return ".png"
    if path.endswith(".jpg") or path.endswith(".jpeg"):
        return ".jpg"
    if path.endswith(".webp"):
        return ".webp"
    return ".img"


def _download(url: str, path: Path, client: httpx.Client) -> bool:
    try:
        response = client.get(url)
        response.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(response.content)
        return True
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Download local logo assets for FE.")
    parser.add_argument("--source", default=str(SOURCE_PATH), help="Path to logo_sources.json")
    parser.add_argument("--dest", default=str(DEST_ROOT), help="Destination root folder")
    args = parser.parse_args()

    source = Path(args.source).resolve()
    dest_root = Path(args.dest).resolve()
    payload = json.loads(source.read_text(encoding="utf-8"))

    downloaded = 0
    skipped = 0
    failed = 0

    headers = {"User-Agent": "EnergyHubLogoDownloader/1.0"}
    with httpx.Client(timeout=40, follow_redirects=True, headers=headers) as client:
        for section_key, folder in [("retailers", "retailers"), ("network_providers", "network")]:
            section = payload.get(section_key, {})
            for key, item in section.items():
                logo_url = item.get("logo_url")
                if not logo_url:
                    skipped += 1
                    continue

                ext = _ext_from_url(logo_url)
                filename = f"{_slugify(key)}{ext}"
                out_path = dest_root / folder / filename
                ok = _download(logo_url, out_path, client)
                if ok:
                    downloaded += 1
                    print(f"[ok] {section_key}/{key} -> {out_path}")
                else:
                    failed += 1
                    print(f"[fail] {section_key}/{key} ({logo_url})")

    print(f"Done. downloaded={downloaded} skipped={skipped} failed={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
