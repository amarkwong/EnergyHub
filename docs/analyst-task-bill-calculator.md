# Analyst Task: Bill Calculator Accuracy (Workstream Active)

Date: 2026-02-11  
Owner: Analyst  
Partner: Full Stack Dev (mandatory day-to-day collaboration)  
Support: Data Engineer (plan/tariff data integrity)

## Goal
Deliver reconciliation-grade calculator logic for retailer plans, with correct handling of:
- plan-specific charges and structures
- tiered solar feed-in rules (first 10 kWh vs after first 10 kWh)
- negative sign treatment for export credits

## Collaboration Protocol (Analyst + Full Stack Dev)
1. Analyst defines expected billing behavior and formula rules.
2. Full Stack Dev implements logic and tests in backend.
3. Analyst validates outputs against invoice evidence.
4. Both jointly sign off each rule before merging.

No calculator rule is considered complete unless:
- Analyst confirms billing interpretation, and
- Full Stack Dev confirms implementation + automated tests.

## Required Outcomes
1. Accurate plan-aware calculator behavior across flat/TOU/solar scenarios.
2. Correct daily tier handling for feed-in:
   - tier 1: first 10 kWh export/day
   - tier 2: export above first 10 kWh/day
3. Export charges are always negative bill credits.
4. Reduced reconciliation deltas on known problematic lines:
   - `Supply charge`
   - `Standard feed-in tariff*`
   - `Next*`
   - `GST` interactions where applicable

## Analyst Deliverables
1. `Calculator Specification` section (below) completed.
2. `Validation Cases` section with at least 10 invoices/fixtures.
3. `Findings & Decisions` log with date-stamped decisions.
4. `Escalations` log for ambiguous tariff wording/source conflicts.

## Full Stack Dev Deliverables (paired)
1. Implement rule updates in calculator/reconciliation code.
2. Add/maintain automated tests for each analyst-approved rule.
3. Provide before/after reconciliation snapshots for review.

## Calculator Specification (Analyst to fill)
### 1) Usage & Supply
- Rule:
- Formula:
- Inputs required:
- Edge cases:

### 2) Controlled Load / Tariff 31
- Rule:
- Formula:
- Inputs required:
- Edge cases:

### 3) Solar Feed-in (Tiered)
- Rule:
- Formula:
- Inputs required:
- Edge cases:

### 4) GST Treatment
- Rule:
- Formula:
- Inputs required:
- Edge cases:

## Validation Cases (Analyst to fill)
| Case ID | Retailer/Plan | Key Feature | Expected | Actual | Pass/Fail | Notes |
|---|---|---|---|---|---|---|
| VC-01 |  |  |  |  |  |  |
| VC-02 |  |  |  |  |  |  |
| VC-03 |  |  |  |  |  |  |

## Findings & Decisions Log
- 2026-02-11: Task initiated. Analyst + Full Stack Dev pairing required.

## Escalations
- Use this section to raise unresolved decisions to Team Lead/user.
- Include: issue, evidence, options, recommendation.

## Definition of Done
- Analyst-approved calculator specification is implemented.
- Automated tests cover all approved rules.
- Reconciliation results materially improve on target invoice fixtures.
- Any remaining discrepancies are documented with root cause and next action.
