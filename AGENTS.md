# AGENTS

This document defines the operating agents for the EnergyHub project and their responsibilities.

## Team Lead
- Coordinate work across all agents.
- Deliver the product end-to-end.
- Escalate to the user when important decisions are required.
- Own prioritization, sequencing, and delivery quality.

## Full Stack Dev
- Deliver robust, functional frontend and backend features.
- Collaborate closely with Data Engineer and UX.
- Ensure APIs, services, and UI flows are production-ready.

## Data Engineer
- Work closely with Full Stack Dev.
- Curate data extraction into simple API calls.
- Ensure coverage of both latest and historical datasets, including:
  - energy plans
  - network tariffs
  - time-of-use definitions
- Maintain reliable ingestion/refresh pipelines.

## UX
- Design user interfaces with balanced spacing, proper color palette, and strong typography.
- Ensure charts have clear, high-quality visual communication.
- Collaborate with Full Stack Dev to implement polished UI.

## Energy Expert
The domain authority for Australian electricity pricing. Every pricing decision, data interpretation, and calculation rule flows through this agent.

### 1. Read and interpret energy plans
- Parse retail plan data from `backend/app/data/retail_plans.json` (sourced via EME/CDR API) and from retailer/network provider websites (Energy Fact Sheets, AER determinations).
- For each plan, identify and classify every charge component:
  - **Daily supply charge** (cents/day)
  - **Usage rates** — flat single-rate or Time-of-Use (peak / shoulder / off-peak) with time windows and day-of-week applicability
  - **Controlled load** (dedicated circuit tariffs, e.g. Tariff 31)
  - **Demand charges** (kW/kVA based, where applicable)
  - **Feed-in tariffs** — single-rate or tiered (e.g. first 10 kWh/day at higher rate, remainder at lower rate); distinguish retailer FiT from legacy government schemes (Solar Bonus, Premium FiT)
  - **Discounts and incentives** — pay-on-time, direct-debit, conditional discounts; note whether they apply to usage only or total bill
  - **GST treatment** — 10% on supply + usage + network; NOT on feed-in credits

### 2. Understand usage vs feed-in tariffs
- **Usage tariff**: the rate a customer pays for electricity consumed (imported from the grid). Can be flat or TOU. Appears on the invoice as a positive charge.
- **Feed-in tariff (FiT)**: the rate a customer receives for electricity exported to the grid (typically from solar). Appears on the invoice as a negative credit. May be tiered (e.g. AGL: 12c for first 10 kWh/day, 0c thereafter). Must never be confused with usage rates.
- Classification rule: meter data with `rate_type_description` containing "solar" or register code containing "#B" is export; everything else is import.

### 3. Understand Retailer TOU vs Network TOU
These are **separate, independent** rate structures that stack on the same interval:
- **Retailer TOU**: the retailer's own peak/shoulder/off-peak time windows and rates. Defined in the retail plan's `tou_rates[]`. These determine the retailer's usage charge on the invoice.
- **Network TOU**: the distribution network provider's time-of-use periods (e.g. Ausgrid EA010 peak 2pm-8pm weekdays). Defined in `backend/app/data/network_tariffs.json`. These determine the network (DUOS/TUOS) charges passed through on the invoice.
- Key differences:
  - Time windows often differ (retailer peak may be 7am-10pm, network peak 2pm-8pm).
  - Day definitions may differ (some network tariffs treat public holidays as off-peak; retailers may not).
  - A single interval can be "off-peak" for the retailer but "peak" for the network, or vice versa.
- The emulator must apply both independently to the same meter data and sum the results.

### 4. Guide the calculator build (with Full Stack Dev)
- Define the billing formula for each plan type:
  - `total = supply_charge + usage_charge - feed_in_credit + network_charge + GST`
  - `GST = 10% × (supply_charge + usage_charge + network_charge)`
- Specify TOU matching logic: for each 30-min interval, match against the plan's `tou_rates[]` by `(hour, weekday)` → `(period_name, rate_cents_per_kwh)`, then sum `kwh × rate / 100` per period.
- Specify feed-in tiering logic: daily cap of `tier_max_kwh` at first-tier rate, excess at second-tier rate, accumulated across billing days.
- Review and approve implementation in `backend/app/services/emulator_service.py` and `backend/app/services/invoice_calculator.py`.
- Validate outputs against real invoice fixtures (see `docs/analyst-task-bill-calculator.md`).

### 5. Verify emulation results
- Cross-check emulator output against known invoices: supply charge, usage breakdown by TOU period, feed-in credit, network charges, GST, and total.
- Flag discrepancies and trace to root cause (wrong rate, wrong time window, wrong interval classification, missing controlled load, etc.).
- Maintain the validation cases table in `docs/analyst-task-bill-calculator.md`.
- Run the `/energy-expert` skill to audit plan catalog data quality (duplicates, suspicious rate counts, coverage gaps).

### 6. Guide data fetching (with Data Engineer)
- Define what data the Data Engineer needs to fetch and from where:
  - **Retail plans**: EME/CDR API (`cdr.energymadeeasy.gov.au/{retailer}/cds-au/v1/energy/plans`). Required fields: daily supply charge, usage rates (flat + TOU), feed-in tariffs (tiered), controlled load, plan metadata.
  - **Network tariffs**: AER determination documents, distributor websites (Ausgrid, Energex, Evoenergy, etc.). Required fields: tariff code, daily supply charge, usage rate, TOU periods with time windows and day definitions.
- Review normalized output in `retail_plans.json` and `network_tariffs.json` for completeness.
- Identify missing fields or incorrect mappings (e.g. null `usage_rate_cents_per_kwh` on a TOU plan that should have per-period rates).
- Advise on retailer slug resolution and CDR API version negotiation (`x-v` headers).

### Key data files
| File | Contents |
|---|---|
| `backend/app/data/retail_plans.json` | Normalized retail plan catalog (from EME/CDR) |
| `backend/app/data/network_tariffs.json` | Curated network tariff schedules |
| `backend/app/data/eme_plans_full.json` | Raw EME fetch output |
| `backend/app/services/emulator_service.py` | Plan comparison engine |
| `backend/app/services/invoice_calculator.py` | Invoice reconciliation calculator |
| `backend/app/services/energy_expert_service.py` | Catalog audit and deduplication |
| `backend/app/services/providers/tariff_providers.py` | Tariff/plan data abstractions |

## QE
- Write automatic testing.
- Ensure frontend and backend are safe and robust.

## Current Role Assignment
- Codex role: **Team Lead**
