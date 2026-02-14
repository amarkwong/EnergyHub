# Tariff and Retail Plan Catalog Sources

Catalog files in this folder are curated snapshots used by the invoice calculator.

- Network tariffs:
  - https://www.aer.gov.au
  - https://www.energex.com.au/manage-your-energy/save-money-and-electricity/tariffs/residential-tariffs
  - https://evoenergy.com.au/Your-Energy/Pricing-and-tariffs/Electricity-network-pricing
  - https://www.ergon.com.au/retail/residential/tariffs-and-prices/compare-residential-tariffs

- Retail plans:
  - https://www.agl.com.au/rates-contracts
  - https://www.agl.com.au/terms-conditions/rates-contracts/energy-price-fact-sheets
  - https://www.energyaustralia.com.au/home/electricity-and-gas/understand-electricity-and-gas-plans/basic-home
  - https://www.originenergy.com.au/fragment/pricing-page-accordions-resi-and-business/
  - https://www.alintaenergy.com.au/residential/electricity-and-gas/plans
  - https://www.redenergy.com.au/electricity-and-gas
  - https://engie.com.au/residential

Sample PDF for OCR testing:
- https://www.agl.com.au/content/dam/digital/agl/documents/help-and-support/agl-bill-explainer-necf-sept2024.pdf

Tariff refresh script:
- Dry run: `./backend/.venv/bin/python backend/scripts/fetch_tariffs.py`
- Write updates: `./backend/.venv/bin/python backend/scripts/fetch_tariffs.py --write --effective-from YYYY-MM-DD`
