"""Inspect retailer/network webpages and extract probable logo asset URLs (svg/png)."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urljoin

import httpx


ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "app" / "data" / "logo_sources.generated.json"


TARGETS = {
    "retailers": {
        "AGL": "https://www.agl.com.au",
        "Origin Energy": "https://www.originenergy.com.au",
        "EnergyAustralia": "https://www.energyaustralia.com.au",
        "Alinta Energy": "https://www.alintaenergy.com.au",
        "Red Energy": "https://www.redenergy.com.au",
        "ENGIE": "https://engie.com.au",
        "1st Energy": "https://www.1stenergy.com.au",
        "Powershop": "https://www.powershop.com.au",
        "dodo": "https://www.dodo.com",
        "ActewAGL": "https://www.actewagl.com.au",
        "Lumo": "https://www.lumoenergy.com.au",
        "Momentum Energy": "https://www.momentumenergy.com.au",
        "BlueNRG": "https://www.bluenrg.com.au",
        "OVO Energy": "https://www.ovoenergy.com.au",
        "Arcline by RACV": "https://www.racv.com.au",
    },
    "network_providers": {
        "ausgrid": "https://www.ausgrid.com.au",
        "endeavour_energy": "https://www.endeavourenergy.com.au",
        "essential_energy": "https://www.essentialenergy.com.au",
        "energex": "https://www.energex.com.au",
        "ergon_energy": "https://www.ergon.com.au",
        "ausnet_services": "https://www.ausnetservices.com.au",
        "citipower": "https://www.citipower.com.au",
        "jemena": "https://www.jemena.com.au",
        "powercor": "https://www.powercor.com.au",
        "united_energy": "https://www.unitedenergy.com.au",
        "evoenergy": "https://www.evoenergy.com.au",
        "tasnetworks": "https://www.tasnetworks.com.au",
    },
}


def extract_logo(html: str, base_url: str) -> str | None:
    candidates: list[str] = []

    # Prefer canonical social preview image if it looks like brand artwork.
    og_match = re.search(
        r"""<meta[^>]+property=["']og:image["'][^>]+content=["']([^"']+)["']""",
        html,
        flags=re.IGNORECASE,
    )
    if og_match:
        candidates.append(urljoin(base_url, og_match.group(1)))

    img_tags = re.findall(r"<img[^>]+>", html, flags=re.IGNORECASE)
    for tag in img_tags:
        lowered = tag.lower()
        if "logo" not in lowered and "brand" not in lowered:
            continue
        src_match = re.search(r"""src=["']([^"']+)["']""", tag, flags=re.IGNORECASE)
        if not src_match:
            continue
        src = src_match.group(1)
        full = urljoin(base_url, src)
        candidates.append(full)

    href_tags = re.findall(r"<link[^>]+>", html, flags=re.IGNORECASE)
    for tag in href_tags:
        lowered = tag.lower()
        if "logo" not in lowered and "icon" not in lowered:
            continue
        href_match = re.search(r"""href=["']([^"']+)["']""", tag, flags=re.IGNORECASE)
        if not href_match:
            continue
        href = href_match.group(1)
        full = urljoin(base_url, href)
        candidates.append(full)

    # Fallback scan for any direct svg/png references that contain logo/brand in URL.
    for match in re.findall(r"""["']([^"']+\.(?:svg|png|webp)(?:\?[^"']*)?)["']""", html, flags=re.IGNORECASE):
        if "logo" in match.lower() or "brand" in match.lower():
            candidates.append(urljoin(base_url, match))

    def rank(url: str) -> tuple[int, int]:
        lower = url.lower()
        ext_score = 0
        if ".svg" in lower:
            ext_score = 3
        elif ".png" in lower:
            ext_score = 2
        elif ".webp" in lower:
            ext_score = 1
        logo_score = 2 if "logo" in lower else (1 if "brand" in lower else 0)
        return (ext_score, logo_score)

    candidates = sorted(set(candidates), key=rank, reverse=True)
    for url in candidates:
        lower = url.lower()
        if ".svg" in lower or ".png" in lower:
            return url
    return candidates[0] if candidates else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract probable logo URLs from target websites.")
    parser.add_argument("--output", default=str(OUT_PATH), help="Output json path")
    args = parser.parse_args()

    output = {
        "metadata": {
            "description": "Automatically extracted logo URLs from provider websites",
        },
        "retailers": {},
        "network_providers": {},
    }

    headers = {"User-Agent": "EnergyHubLogoExtractor/1.0"}
    with httpx.Client(timeout=30, follow_redirects=True, headers=headers) as client:
        for group, entries in TARGETS.items():
            for name, url in entries.items():
                logo_url = None
                try:
                    response = client.get(url)
                    response.raise_for_status()
                    logo_url = extract_logo(response.text, str(response.url))
                except Exception:
                    logo_url = None

                output[group][name] = {
                    "website": url,
                    "logo_url": logo_url,
                    "format": "svg" if logo_url and ".svg" in logo_url.lower() else ("png" if logo_url and ".png" in logo_url.lower() else None),
                }

    out_path = Path(args.output).resolve()
    out_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
