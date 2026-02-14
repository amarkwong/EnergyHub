# EnergyHub Team-Lead Execution Plan

Date: 2026-02-09
Owner: Team Lead

## Goal
Deliver three parallel tracks:
1. Validate NEM12 parsing against real public examples for 5/15/30 minute intervals.
2. Build production-grade invoice calculation and invoice parsing pipeline.
3. Finalize a deployable AWS hosting architecture and rollout plan.

## Squad Structure (Subagent Workstreams)

### Subagent A: Meter Data Validation (NEM12)

#### Scope
- Build test fixtures for 5-minute, 15-minute, and 30-minute interval NEM12 files.
- Add automated parser validation and edge-case tests.

#### Public source set
- AEMO MDFF NEM12/NEM13 v2.7 (effective 1 Dec 2025):
  - Appendix H.1 includes explicit 30-minute NEM12 sample rows.
  - Appendix H.9 includes explicit 5-minute NEM12 sample rows.
  - URL: https://www.aemo.com.au/-/media/files/electricity/nem/retail_and_metering/market_settlement_and_transfer_solutions/2025/mdff-specification-nem12-nem13-v27.pdf?rev=9d9baf6940594142a691f75b13433779&sc_lang=en
- AEMO NEM12/NEM13 file test process (Scenario 5: change from 15-minute to 30-minute intervals):
  - URL: https://www.aemo.com.au/-/media/files/electricity/nem/retail_and_metering/metering-procedures/2017/nem12-and-nem13-file-testing.pdf?rev=83be0855c2434eff8def34b801602c54&sc_lang=en

#### Delivery tasks
- Create `backend/tests/fixtures/nem12_5m.csv` from Appendix H.9 rows.
- Create `backend/tests/fixtures/nem12_30m.csv` from Appendix H.1 rows.
- Create `backend/tests/fixtures/nem12_15m.csv` by reconstructing a valid scenario-5 style file (15-minute day blocks) and document provenance in fixture header comments.
- Add tests for:
  - expected interval counts per day (288/96/48)
  - date boundaries and sorting
  - peak/off-peak classification consistency
  - malformed row tolerance

#### Acceptance criteria
- `pytest backend/tests/test_nem12.py -v` passes with 5m/15m/30m fixtures.
- Parser returns correct `interval_length` and total interval counts for all fixture types.

---

### Subagent B: Invoice Module (Calculator + OCR Parser)

#### Scope
- Replace placeholder tariff logic with source-driven tariff ingestion.
- Add retailer plan ingestion (BPID/Energy Fact Sheet fields).
- Make OCR parser process real invoice-style PDFs.

#### Tariff and plan source set
Network tariffs (authoritative):
- AER pricing proposals and decisions (approved network tariff schedules):
  - Ausgrid 2025-26 proposal/decision pages
  - Energex 2025-26 decision page
  - Root domain: https://www.aer.gov.au
- Distributor tariff pages (operational detail / identifiers):
  - Energex residential tariffs: https://www.energex.com.au/manage-your-energy/save-money-and-electricity/tariffs/residential-tariffs
  - Evoenergy network pricing: https://evoenergy.com.au/Your-Energy/Pricing-and-tariffs/Electricity-network-pricing

Retail plans:
- Retailer BPID/EFS entry points:
  - AGL rates/contracts + energy fact sheets: https://www.agl.com.au/rates-contracts and https://www.agl.com.au/terms-conditions/rates-contracts/energy-price-fact-sheets
  - EnergyAustralia standing offer + BPID references: https://www.energyaustralia.com.au/home/electricity-and-gas/understand-electricity-and-gas-plans/basic-home
  - Origin pricing/BPID entry point: https://www.originenergy.com.au/fragment/pricing-page-accordions-resi-and-business/

OCR PDF fixture (public):
- AGL sample bill explainer PDF (contains invoice-like line items and totals):
  - https://www.agl.com.au/content/dam/digital/agl/documents/help-and-support/agl-bill-explainer-necf-sept2024.pdf

#### Delivery tasks
- Implement `TariffProvider` abstraction:
  - `NetworkTariffProvider` (AER/distributor feeds)
  - `RetailPlanProvider` (BPID/EFS normalized model)
- Normalize tariff model:
  - daily charge
  - TOU periods
  - demand components
  - controlled load
  - GST applicability
- Refactor calculator to consume normalized tariff/plan objects.
- Implement OCR extraction path:
  - pdf-to-image + tesseract
  - parser confidence scoring
  - field-level fallback rules
- Add golden test for AGL sample bill explainer PDF.

#### Acceptance criteria
- Invoice calculator output changes when tariff source data changes (no hardcoded default rates).
- OCR parser extracts: invoice number, billing period, line items, subtotal, GST, total from sample PDF with confidence threshold.
- Reconciliation endpoint works end-to-end with uploaded NEM12 + parsed invoice + selected tariff.

---

### Subagent C: DevOps / Hosting Plan

#### Scope
Design and implement a production-ready AWS topology with secure CI/CD, observability, data durability, and staged rollout.

#### Target architecture
- Runtime: ECS Fargate services for backend + frontend.
- Edge: CloudFront + WAF + ACM TLS + Route53.
- Ingress: ALB private/public split with path-based routing.
- Data: RDS PostgreSQL (Multi-AZ in prod), Secrets Manager, encrypted EBS.
- Storage: S3 for uploads and artifacts (replace local volume for uploads).
- Async: SQS for OCR/reconciliation jobs (optional phase 2).
- Observability: CloudWatch logs/metrics/alarms + X-Ray/OpenTelemetry.
- Security: IAM least privilege, KMS encryption, SG minimization, AWS Config guardrails.

#### Delivery tasks
- Terraform hardening:
  - remote state backend (S3 + DynamoDB lock)
  - separate workspaces/accounts for dev/stage/prod
  - module inputs for HA toggles
- CI/CD hardening:
  - image scan gate
  - IaC plan/apply with approvals
  - progressive deployment (blue/green on ECS)
- App deployment changes:
  - env config via SSM/Secrets Manager
  - health checks + autoscaling policies

#### Acceptance criteria
- `terraform plan` clean for dev/stage/prod.
- Blue/green deploy and rollback runbook validated.
- RPO/RTO and SLOs documented with alarm thresholds.

---

## Cross-Track Engineering Rules
- Stop using in-memory stores for shared business state (move to persistent DB/repository layer).
- Add idempotent file IDs and object storage metadata.
- Ensure API schemas and returned payloads are strictly aligned.
- Remove committed `node_modules` and Python cache artifacts from git tracking.

## Milestones
- M1 (Week 1): NEM12 fixtures + parser test expansion, tariff/provider interfaces, infra target design doc.
- M2 (Week 2): live tariff ingestion MVP + OCR pipeline with real PDF fixture + staging infra baseline.
- M3 (Week 3): reconciliation E2E hardening + production readiness checklist + rollout go/no-go.

## Immediate Next Actions (Today)
1. Subagent A: commit 5m/15m/30m fixtures + parser tests.
2. Subagent B: implement tariff provider interfaces and remove hardcoded rates.
3. Subagent C: produce `infrastructure/terraform/PROD_PLAN.md` with phased migration steps and cost envelope.
