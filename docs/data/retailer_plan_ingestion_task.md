# Data Engineer Task: Full Retailer Plan Ingestion from EME/CDR

Date: 2026-02-11  
Owner: Data Engineering  
Priority: High

## Goal
Build a production-grade ingestion job that fetches detailed electricity plan data for every retailer shown in the Energy Made Easy retailer dropdown, and produces:

1. Plan-level dataset (all available plans per retailer).
2. Retailer-level coverage summary:
   - customer segment served: `RESIDENTIAL`, `BUSINESS`, or `BOTH`
   - serving states/territories: `NSW`, `VIC`, `QLD`, `SA`, `TAS`, `ACT`, `NT`, `WA` (where available)

## Inputs
- Retailer list source: HTML dropdown provided by product team (Energy Made Easy UI dump).
- API source: `https://cdr.energymadeeasy.gov.au/{retailer_slug}/cds-au/v1/energy/plans` and detail endpoint.
- Existing reference script:
  - `/Users/feifan.wang@flightcentre.com/Personal/EnergyHub/backend/scripts/fetch_eme_plans.py`

## Known Issue To Fix
Current error seen during some requests:

`{"errors":[{"code":"urn:au-cds:error:cds-all:Header/Missing","title":"Missing Required Header","detail":"Header x-v must be provided"}]}`

### Required request behavior
- Send `x-v` on **every** API request (list and detail).
- Send `Accept: application/json`.
- Add stable `User-Agent` (e.g. `EnergyHubPlanIngestion/1.0`).
- Keep version negotiation:
  - list endpoint starts at `x-v: 1`
  - detail endpoint starts at `x-v: 3`
  - if `UnsupportedVersion`, retry with advertised min/max.

## Execution Requirements
1. Parse retailer names from the provided HTML dropdown.
2. Resolve each name to a CDR retailer slug/base URI.
3. For each resolved retailer slug:
   - paginate list endpoint until complete
   - fetch detail for each `planId`
   - persist raw + normalized records
4. Extract/derive:
   - `customer_type` (from plan fields)
   - state coverage (from geography/postcode/network/distributor fields; document derivation logic)
5. Aggregate retailer summary:
   - `serves_residential` boolean
   - `serves_business` boolean
   - `serves_both` boolean
   - `serving_states` array

## Deliverables
1. `/Users/feifan.wang@flightcentre.com/Personal/EnergyHub/backend/app/data/eme_plans_full.json`
   - normalized plan-level output (all fetched retailers)
2. `/Users/feifan.wang@flightcentre.com/Personal/EnergyHub/backend/app/data/eme_retailer_coverage.json`
   - retailer-level summary (`segment`, `serving_states`, stats)
3. `/Users/feifan.wang@flightcentre.com/Personal/EnergyHub/docs/data/eme_ingestion_runbook.md`
   - how mapping was done
   - any unresolved retailers
   - retry/error strategy
   - data caveats

## Output Schema (minimum)
### Plan row
- `retailer_name`
- `retailer_slug`
- `plan_id`
- `plan_name`
- `fuel_type`
- `customer_type`
- `effective_from`
- `effective_to`
- `tariff_structure` (flat/tou/demand/mixed)
- `daily_supply_charge`
- `usage_components` (full component object, not flattened only)
- `source_url`
- `ingested_at_utc`

### Retailer summary row
- `retailer_name`
- `retailer_slug`
- `serves_residential`
- `serves_business`
- `serves_both`
- `serving_states`
- `plans_count`
- `last_successful_ingestion_utc`
- `notes`

## Acceptance Criteria
- >= 95% of dropdown retailers are either:
  - successfully mapped and ingested, or
  - explicitly listed as unresolved with reason.
- No request should fail due to missing `x-v`.
- For mapped retailers, at least one successful plan-list call is recorded.
- Retailer summary includes segment and state coverage for all mapped retailers.
- Job is rerunnable and idempotent.

## Nice-to-have
- Add exponential backoff + jitter for transient DNS/network failures.
- Save per-retailer fetch diagnostics (`http_status_counts`, `errors`, `duration_ms`).
- Add unit test for header injection and version negotiation.
