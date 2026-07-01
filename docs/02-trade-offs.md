# Crosscheck — Trade-offs

Each of these was a real decision point during the build, not a
retroactive justification. Where relevant, I've noted what would change
this decision at greater scale.

## 1. Heuristic income estimation vs. Plaid's Bank Income product

**Decision:** built a simple, transparent heuristic (find recurring,
similarly-sized deposits, annualize them) rather than using Plaid's
dedicated Bank Income product.

**Why:** Plaid's Bank Income product requires a separate `/user/create`
flow, explicit access approval (their docs say to contact an account
manager if a user token isn't issued automatically), a different Link
flow, and is billed per use in production. That's real friction and real
cost for a v1. The heuristic needed zero extra setup beyond what we'd
already verified working (`transactions_sync`), and — importantly — is
fully explainable: every risk score traces back to a specific, inspectable
piece of evidence (see `plaid_evidence` in every pipeline run), not a
number from a black box.

**What would change this:** at real scale, with real users and real
accuracy requirements, Plaid's product almost certainly outperforms a
hand-rolled heuristic (it handles multiple income streams, irregular pay
schedules, gig income, etc. — ours doesn't). The honest path is: ship the
heuristic, instrument how often it disagrees with ground truth in
production, and use that data to justify (or not) the switch to a paid
product.

## 2. Real historical financial data + synthetic identity, not fully synthetic data

**Decision:** the 9,578 `loan_applications` rows use *real* historical
income, FICO, DTI, and repayment outcomes from a public LendingClub-derived
dataset, with synthetically generated names/employers layered on top
(since the public dataset strips identity for privacy).

**Why:** genuinely messy real data was a project requirement. Fully
synthetic data (e.g., income drawn from a clean random distribution) would
have been easier to build but wouldn't have tested anything — real income
distributions are messy in ways that are hard to fake convincingly. Using
real historical data for the financial signal, with synthetic identity
layered only where the real data had none, kept the "real messy public
data" requirement honest while still being usable.

## 3. Decorrelated variance for Plaid vs. document data

**Decision:** the synthetic Plaid income and the synthetic document income
use *independently seeded* variances from the applicant's stated income,
not the same variance applied twice.

**Why:** if both signals moved together, "two independent sources
corroborate" would be meaningless — it would really be one signal
duplicated twice. With independent seeds, some applicants have both
sources agree, some have them disagree, some have only one flag a
concern. That's a realistic and useful evaluation surface, and it's what
actually let the eval harness produce a non-trivial confusion matrix
(TP/FP/FN/TN all populated, not just perfect agreement).

## 4. Regex/text-based document parsing, not OCR

**Decision:** documents are generated and parsed as machine-readable PDF
text (via `pdfplumber` + regex over known label variants), not scanned
images requiring OCR.

**Why:** OCR accuracy is its own large, separate engineering problem
(image preprocessing, handling skewed scans, handwriting, etc.). Building
it well would have consumed the whole project without adding much signal
about the actual bottleneck (income cross-checking). The parser does
handle real format variety (three different label wordings across three
different simulated payroll systems), which was the realistic "messiness"
worth testing.

## 5. Transparent, hand-weighted risk score, not a trained model

**Decision:** `risk_score` is a weighted sum (50% income discrepancy, 30%
credit score, 20% DTI) with explicit, documented weights — not a model
trained on labeled outcomes.

**Why:** we *do* have real historical outcome data (`not_fully_paid`) that
a real version of this would train against. But building and validating a
calibrated model is a materially different, larger scope of work than
building the verification pipeline itself, and conflating the two would
have diluted both. The transparent heuristic is also arguably *better*
for a v1 in a regulated space like lending — every score is fully
explainable to a human reviewer, which a trained model's weights are not,
without additional interpretability work.

**What would change this:** see `standardization.md` — this is the single
highest-value next step if this were going to more customers.

## 6. Forcing "needs_review" on weak evidence, not trusting a low risk score

**Decision:** if Plaid or document confidence is too low, the decision is
forced to `needs_review` regardless of what the numeric risk score would
otherwise say — even though the risk-score formula, as built, actually
*increases* risk when evidence is missing (rather than defaulting to a
neutral middle value).

**Why:** a low risk score born from missing data isn't the same as a low
risk score born from genuine corroborating evidence, and conflating the
two would let real risk slip through unflagged. This was a specific
design choice made after noticing the risk-score formula's own logic
needed a backstop.

## 7. Synchronous, blocking `/verify` endpoint

**Decision:** the `POST /applications/{id}/verify` endpoint runs the full
pipeline (including a 10-40+ second Plaid retry loop) synchronously and
returns the result directly, rather than queuing it as a background job.

**Why:** simpler to build and verify for a v1, and Plaid Sandbox response
times (observed 8-15 seconds per full pipeline run) were tolerable for
manual testing and a small eval harness. This would not hold up under
real production load or a real UI waiting on the response.

**What would change this:** see `standardization.md`.
