# Crosscheck — What I'd Standardize for 10 More Customers

Everything below is scoped to the specific question: if a second, third,
... tenth lender wanted to run something like this, what in the current
build is a v1 shortcut that wouldn't survive that, and what would the
standardized version look like?

## 1. Risk score calibration

**Current state:** hand-picked weights (50/30/20), documented as a
heuristic, not tuned against outcomes.

**Standardize to:** train the weighting (or replace the whole scoring
step with a small classifier) against real labeled outcome data. We
already have exactly this kind of label sitting unused for this purpose —
the `not_fully_paid` column in the real historical dataset. The honest
next step is a proper train/test split against that column, measuring
whether the resulting model's risk ordering actually predicts default
better than the current heuristic, not just declaring it does.

## 2. Secrets and credential handling

**Current state:** Plaid `access_token` values are stored in Postgres as
plaintext (flagged explicitly in `init.sql`), and API keys live in a
`.env` file.

**Standardize to:** encrypt `access_token` at rest (e.g., via
`pgcrypto` or an application-level encryption layer), move secrets to a
proper secrets manager (AWS Secrets Manager, GCP Secret Manager, or
Vault) instead of `.env` files, and rotate any keys that touched a local
`.env` during development before ever approaching production.

## 3. Async job handling for the `/verify` endpoint

**Current state:** synchronous, blocking HTTP endpoint; a single request
can take 10-40+ seconds due to Plaid's retry-until-ready pattern.

**Standardize to:** a proper job queue (e.g., Celery, or LangGraph's own
persistence/checkpoint features) where `POST /verify` returns immediately
with a job ID, and the client polls or receives a webhook when the
verification completes. This also opens the door to retrying a failed
Plaid call without re-running the entire pipeline from scratch.

## 4. Database schema migrations

**Current state:** a single `init.sql` applied once at container startup.
Any schema change requires manually altering a running database.

**Standardize to:** a real migration tool (Alembic is the natural choice
given the Python/Postgres stack) so schema changes are versioned,
reviewable, and safely applicable to a database that already has real
customer data in it.

## 5. Connection handling

**Current state:** every function opens a fresh `psycopg2` connection
and closes it — fine at the traffic volume this was tested at, wasteful
and eventually rate-limiting at real scale.

**Standardize to:** a connection pool (e.g., `psycopg2.pool` or moving to
an async driver with proper pooling) shared across requests.

## 6. Multi-tenancy

**Current state:** single implicit tenant — no concept of "which lender
does this applicant belong to."

**Standardize to:** a `tenant_id` on every table, tenant-scoped API
authentication, and query-level enforcement that one lender's data is
never visible to another's requests. This is a foundational change, not
a bolt-on — worth deciding early if a second real customer is likely.

## 7. Observability

**Current state:** print statements and manual inspection (which was
essential for building this, but doesn't scale to a running service).

**Standardize to:** structured logging (with request IDs tying a single
verification run's logs together across all six pipeline nodes),
metrics on Plaid call latency/failure rate, and alerting on elevated
`needs_review`-due-to-weak-evidence rates (which would indicate a Plaid
or document-parsing regression before a human notices).

## 8. Document handling

**Current state:** generated/parsed as local files on the container's
filesystem, handles one PDF text layout family via regex.

**Standardize to:** object storage (S3-compatible) instead of local
disk, and a real extraction pipeline that combines the current
regex-over-text approach with OCR fallback for scanned documents,
rather than assuming all incoming documents have machine-readable text.

## 9. Testing

**Current state:** extensive *manual* verification (real data in, real
output checked by hand at every stage) but no automated test suite.

**Standardize to:** a `pytest` suite covering the pure-logic pieces
(`income_estimator`, `crosscheck`, `risk_score`, `decision`,
`variance`) with fixed inputs and asserted outputs, run in CI on every
change — turning the manual verification discipline used throughout this
build into something that keeps verifying itself automatically going
forward.

## 10. Plaid product reconsideration

**Current state:** custom heuristic income estimation (see
`trade-offs.md` for the reasoning).

**Standardize to:** once there's real production traffic and real
accuracy data on how often the heuristic disagrees with ground truth,
revisit whether Plaid's Bank Income product is worth the added cost and
integration complexity. This isn't a "do it now" item — it's a
"instrument now, decide later with data" item.
