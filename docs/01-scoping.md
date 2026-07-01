# Crosscheck — Scoping Document

## The problem

Loan underwriting requires verifying that a borrower's stated income is
real. In practice, an underwriter cross-references three things: what the
applicant *typed* on the application, what their *bank transactions*
actually show, and what their *submitted documents* (pay stubs, bank
statements) say. Doing this by hand, for every application, is exactly the
kind of tedious, error-prone, high-volume task that eats a junior
underwriter's day — and it's the specific bottleneck this project targets.

**Crosscheck's one job:** given a loan applicant, pull their stated income,
their bank-verified income (via Plaid), and their document-extracted
income, compare all three, and produce a risk score and a decision
(`verified` / `flagged` / `needs_review`) with a plain-language
justification a human can act on.

## Why this vertical, why this bottleneck

Fintech/lending was chosen because it has three properties that make it a
good target for a real "forward-deployed" build:

1. **Real public data exists** without requiring a data-sharing agreement
   or a login-gated download (a 9,578-row LendingClub-derived dataset with
   real historical income, FICO, DTI, and repayment outcomes).
2. **Real infrastructure exists to integrate with** — Plaid is literally
   what real lenders use for bank-verified income, and its Sandbox
   environment gives real authenticated API access without needing
   production approval.
3. **The bottleneck is narrow enough to build well.** Full underwriting
   (credit decisioning, pricing, compliance checks) is a much bigger,
   fuzzier problem. Income verification specifically has clear inputs,
   clear outputs, and a clear "did this help" question.

## What's in scope

- Pulling an applicant's stated financial data from a real historical
  dataset
- Connecting to Plaid Sandbox and estimating income from real (simulated)
  bank transaction data, per applicant
- Generating and parsing realistic synthetic pay stub documents
- Cross-checking all three sources and computing a transparent risk score
- Producing a decision with a human-readable justification
- An eval harness that measures accuracy against known ground truth
- A containerized, deployable service (FastAPI + Docker)

## What's explicitly out of scope (and why)

- **Full credit/underwriting decisioning.** Crosscheck answers "does the
  stated income check out," not "should this loan be approved." Those are
  different questions with different stakeholders and different
  regulatory considerations.
- **Real bank connections / real applicant PII.** Everything here runs
  against Plaid *Sandbox* and synthetic identities layered on real
  financial data. This was a deliberate choice to keep the project legally
  and ethically simple while still exercising real infrastructure.
- **A calibrated risk model.** The risk-scoring weights are a transparent,
  reasoned starting heuristic, not a model trained on outcome data. See
  `trade-offs.md` for why, and `standardization.md` for what a calibrated
  version would require.
- **OCR / scanned-document support.** Documents are parsed as
  machine-readable PDF text, not scanned images. A real system would need
  to handle both.
- **Plaid's dedicated Bank Income product.** Considered and explicitly
  rejected for v1 — see `trade-offs.md`.

## Success criteria

- The full pipeline runs end-to-end against real applicants, real Plaid
  Sandbox data, and real generated documents, with every claim in this
  writeup backed by something actually run and observed, not asserted.
- The eval harness produces real precision/recall/F1 numbers against known
  ground truth (not just "it looked right in a demo").
- The system is containerized and runs via `docker compose up`, not just
  on one developer's laptop with a pile of manually-run scripts.
