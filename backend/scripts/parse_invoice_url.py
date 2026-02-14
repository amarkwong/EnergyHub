"""Download a public invoice PDF and parse it with InvoiceParser."""
import argparse
import asyncio
import json

import httpx

from app.services.invoice_parser import InvoiceParser


DEFAULT_URL = "https://www.agl.com.au/content/dam/digital/agl/documents/help-and-support/agl-bill-explainer-necf-sept2024.pdf"


async def main(url: str) -> None:
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(url)
        response.raise_for_status()

    parser = InvoiceParser()
    result = await parser.parse_invoice("invoice-from-url", response.content)
    print(json.dumps(result, default=str, indent=2))


if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("--url", default=DEFAULT_URL, help="Public PDF URL")
    args = arg_parser.parse_args()
    asyncio.run(main(args.url))
