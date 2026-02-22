# Energy Expert

Domain authority for Australian electricity pricing. Interprets energy plans, verifies calculator/emulator results, audits data quality, and guides data fetching.

## Role reference

See `AGENTS.md` → **Energy Expert** for the full responsibility definition.

## Instructions

When this skill is invoked, determine which mode the user needs and execute it.

### Mode 1: Catalog audit (default if no specific request)

1. Read `backend/app/data/retail_plans.json` and count total plans and TOU rate entries.

2. Run the audit:
   ```bash
   cd /Users/feifan.wang@flightcentre.com/Personal/EnergyHub && python3 -c "
   import json
   from backend.app.services.energy_expert_service import EnergyExpertService
   data = json.loads(open('backend/app/data/retail_plans.json').read())
   plans = data.get('plans', [])
   report = EnergyExpertService.audit_catalog(plans)
   print(json.dumps(report, indent=2))
   "
   ```

3. Report findings:
   - Total plans analysed
   - Plans with duplicate TOU rates (list retailer + plan name + count)
   - Plans with suspicious rate counts (>10 entries)
   - Plans with missing weekday/weekend coverage
   - Total duplicate rates found

4. If duplicates are found, ask the user if they want to fix them. If yes, run:
   ```bash
   cd /Users/feifan.wang@flightcentre.com/Personal/EnergyHub && python3 -c "
   import json
   from backend.app.services.energy_expert_service import EnergyExpertService
   path = 'backend/app/data/retail_plans.json'
   data = json.loads(open(path).read())
   EnergyExpertService.normalize_plan_catalog(data.get('plans', []))
   open(path, 'w').write(json.dumps(data, indent=2))
   print('Catalog normalised.')
   "
   ```

5. Re-run the audit to confirm 0 duplicate rates remain.

### Mode 2: Interpret a specific plan

When the user asks about a specific retailer or plan:

1. Search `backend/app/data/retail_plans.json` for matching plans by retailer name or plan name.

2. For each matched plan, explain in plain language:
   - **Tariff type**: flat or TOU
   - **Daily supply charge**: X cents/day ($Y/quarter)
   - **Usage rates**: if flat, the single rate; if TOU, list each period with name, time window, days, and rate
   - **Feed-in tariffs**: list each tier with rate and daily cap (if any); note whether it is retailer FiT or legacy government scheme
   - **Controlled load**: if present, the dedicated circuit rate
   - **Discounts**: any conditional discounts and what they apply to

3. If the plan has TOU rates, also check `backend/app/data/network_tariffs.json` for the relevant network tariff and highlight where retailer TOU windows differ from network TOU windows.

### Mode 3: Verify emulation result

When the user provides an emulation result or asks to verify a bill calculation:

1. Read the emulation output (from API response or user-provided data).

2. For the plan in question, independently calculate:
   - Supply charge = `daily_supply_charge_cents × billing_days / 100`
   - Usage charge = sum of `(kwh_per_period × rate_cents_per_kwh / 100)` for each TOU period (or flat rate × total import kWh)
   - Feed-in credit = apply tiered logic: first `tier_max_kwh × billing_days` at tier-1 rate, remainder at tier-2 rate
   - Network charge = network daily supply + network usage (flat or TOU)
   - GST = `10% × (supply + usage + network)` — never on feed-in credit
   - Total = `supply + usage - feed_in_credit + network + GST`

3. Compare each line item against the emulation output. Flag any discrepancy with:
   - Which line item is wrong
   - Expected value vs actual value
   - Likely root cause (wrong rate, wrong time window mapping, wrong interval classification, missing component)

4. If checking against a real invoice, also note any invoice line items the emulator does not yet model (e.g. controlled load, demand charges, late fees).

### Mode 4: Guide data fetching

When the user or Data Engineer needs guidance on what data to fetch:

1. **Retail plans** — advise on EME/CDR API usage:
   - Endpoint: `https://cdr.energymadeeasy.gov.au/{retailer_slug}/cds-au/v1/energy/plans`
   - Required headers: `x-v` (list: `1`, detail: `3`), `Accept: application/json`
   - Required fields to extract: daily supply charge, usage rates (flat + per-period TOU), feed-in tariffs (tiered), controlled load, plan metadata (effective dates, customer type, fuel type)
   - Reference script: `backend/scripts/fetch_eme_plans.py`

2. **Network tariffs** — advise on sources:
   - AER determination documents for each distributor
   - Distributor websites (Ausgrid, Energex, Evoenergy, Jemena, CitiPower, Powercor, United Energy, AusNet, Essential, Endeavour, Ergon, TasNetworks)
   - Required fields: tariff code, tariff name, daily supply charge, usage rate, TOU periods (name, start_time, end_time, days, rate)

3. Review the normalized output files for completeness:
   - `backend/app/data/retail_plans.json` — check for null rates on TOU plans, missing feed-in tiers, zero supply charges
   - `backend/app/data/network_tariffs.json` — check for missing TOU periods, mismatched tariff codes

### Mode 5: Calculator specification

When the user asks to define or review calculator rules:

1. Reference `docs/analyst-task-bill-calculator.md` for the specification template.

2. For each calculator section (Usage & Supply, Controlled Load, Solar Feed-in, GST), define:
   - **Rule**: plain-language description of billing behavior
   - **Formula**: mathematical expression with variable names matching code
   - **Inputs required**: which fields from `retail_plans.json` / `network_tariffs.json` / meter data
   - **Edge cases**: zero export, no TOU rates on a TOU plan, multi-tier feed-in with daily cap, plans with no supply charge

3. After defining rules, review the implementation in:
   - `backend/app/services/emulator_service.py` (plan comparison engine)
   - `backend/app/services/invoice_calculator.py` (invoice reconciliation)
   - `backend/app/services/providers/tariff_providers.py` (data models)

4. Flag any gap between the specification and the implementation.

## Key domain concepts

| Concept | Definition |
|---|---|
| **Import (usage)** | Electricity consumed from the grid. Meter register `#A` or rate_type without "solar". Positive charge. |
| **Export (feed-in)** | Electricity sent to the grid (solar). Meter register `#B` or rate_type containing "solar". Negative credit. |
| **Retailer TOU** | The retailer's own peak/shoulder/off-peak windows and rates. From `tou_rates[]` in plan data. |
| **Network TOU** | The distributor's time-of-use periods. From `network_tariffs.json`. Independent of retailer TOU. |
| **DUOS/TUOS** | Distribution/Transmission Use of System charges. The network component of a bill. |
| **Controlled load** | Dedicated circuit (e.g. hot water) on a separate tariff, typically cheaper flat rate. |
| **Demand charge** | Charge based on peak kW/kVA demand in a billing period, not just kWh consumed. |
| **GST** | 10% on supply + usage + network charges. Never applied to feed-in credits. |
| **EME/CDR** | Energy Made Easy / Consumer Data Right — the AER-hosted API for retail plan data. |

## Key files

| File | Purpose |
|---|---|
| `backend/app/data/retail_plans.json` | Normalized retail plan catalog |
| `backend/app/data/network_tariffs.json` | Curated network tariff schedules |
| `backend/app/data/eme_plans_full.json` | Raw EME fetch output |
| `backend/app/services/emulator_service.py` | Plan comparison engine |
| `backend/app/services/invoice_calculator.py` | Invoice reconciliation calculator |
| `backend/app/services/energy_expert_service.py` | Catalog audit and deduplication |
| `backend/app/services/providers/tariff_providers.py` | Tariff/plan data abstractions |
| `docs/analyst-task-bill-calculator.md` | Calculator specification and validation cases |
| `docs/data/retailer_plan_ingestion_task.md` | Data Engineer ingestion task spec |
| `AGENTS.md` | Full agent role definition |
