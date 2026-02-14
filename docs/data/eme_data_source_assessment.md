# Energy Made Easy Data Source Assessment

Date run: 2026-02-11
Workspace: /Users/feifan.wang@flightcentre.com/Personal/EnergyHub

## Objective
Validate whether Energy Made Easy can be used as a reliable source for retailer energy plans and pricing components needed by invoice reconciliation.

## Source validated
- Official host: https://cdr.energymadeeasy.gov.au
- Program context: AER Energy Product Reference Data (CDR Product APIs)
- Confirmed endpoint family:
  - `/{retailer}/cds-au/v1/energy/plans`
  - `/{retailer}/cds-au/v1/energy/plans/{planId}`

## Live API findings
- The API is reachable and returns plan data successfully.
- CDR version header is mandatory:
  - Missing `x-v` returns HTTP 400 (`Header x-v must be provided`).
- Version differs by endpoint type:
  - List endpoint currently accepts `x-v: 1`.
  - Plan detail endpoint tested required at least `x-v: 3`.
- Detail responses include fields needed for normalization:
  - `electricityContract.tariffPeriod[].dailySupplyCharge`
  - unit prices inside rate blocks (single-rate and TOU structures)

## Data quality notes
- Plan list gives broad coverage and metadata (`planId`, `displayName`, `fuelType`, `customerType`, `effectiveFrom`).
- Some TOU plans do not expose a single flat usage rate, so `usage_rate_cents_per_kwh` may be `null` in a flattened schema.
- A production loader should keep richer tariff structures (TOU periods, controlled load, feed-in, demand) instead of forcing one rate.

## Deliverables produced
- Fetch script: `/Users/feifan.wang@flightcentre.com/Personal/EnergyHub/backend/scripts/fetch_eme_plans.py`
- Sample output: `/Users/feifan.wang@flightcentre.com/Personal/EnergyHub/backend/app/data/eme_plans_sample.json`

## Run command used
```bash
python3 backend/scripts/fetch_eme_plans.py \
  --retailers agl,origin,energyaustralia \
  --max-plans 5 \
  --page-size 5 \
  --fuel-type ELECTRICITY \
  --output backend/app/data/eme_plans_sample.json
```

## Result snapshot
- Normalized plans written: 15 total (5 per retailer).
- Retailers tested: `agl`, `origin`, `energyaustralia`.

## Recommendation
Use this API as the primary source for retailer plans in the current system. For reconciliation-grade accuracy, next iteration should store full contract component structures per plan (not only flattened daily/usage fields) and map them to invoice line-item categories.
