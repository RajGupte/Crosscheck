# Crosscheck

**An income verification agent for loan underwriting.**

Crosscheck cross-checks a loan applicant's *stated* income against two
independent, real sources — bank transaction data (via Plaid) and a
submitted pay stub document — and produces a risk score and decision
(`verified` / `needs_review` / `flagged`) with a plain-language
justification a human underwriter can act on.

It's built as a real forward-deployed-engineer exercise: real messy public
data, a real external API with real authentication, a real agent pipeline,
a real eval harness with measured accuracy, and a real deployable
(Dockerized) service — not a demo assembled from mocked pieces.

---

## What it actually does

Given an applicant, Crosscheck:

1. Pulls their **stated income** from a real historical loan dataset
2. Connects to **Plaid** (Sandbox) and estimates their real income from
   simulated bank transaction patterns — recurring, similarly-sized
   deposits, annualized
3. Generates and parses a **pay stub PDF** for that applicant, extracting
   income and employer via text parsing (handling multiple realistic
   label formats)
4. **Cross-checks** all three sources against each other
5. Computes a transparent, weighted **risk score**
6. Produces a **decision** with a full justification trail

Every number in the output traces back to something inspectable — no
black-box scoring.

## Screenshot

The UI lets you run a verification for any applicant and see the full
breakdown: decision badge, risk score, a three-source income comparison
table, and the reasoning behind the call.

## Architecture

```
                    ┌─────────────────┐
                    │   Web UI / API   │   FastAPI (app/api/)
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  LangGraph Agent  │   app/agent/graph.py
                    │  (6 sequential    │
                    │   nodes)          │
                    └────────┬─────────┘
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌──────────────────┐
│   PostgreSQL     │ │  Plaid Sandbox   │ │  Generated PDF    │
│ (stated income,  │ │ (bank-verified   │ │  pay stubs         │
│  real historical │ │  income,         │ │  (document-        │
│  loan data)      │ │  per-applicant)  │ │  extracted income) │
└─────────────────┘ └─────────────────┘ └──────────────────┘
```

**The six-node pipeline** (`app/agent/nodes/`):

| Node | Job |
|---|---|
| `fetch_application` | Pull stated income/employer/FICO/DTI from Postgres |
| `fetch_plaid` | Create a per-applicant Plaid Sandbox connection, pull transactions, estimate income |
| `parse_documents` | Generate + parse a synthetic pay stub PDF |
| `crosscheck` | Compare all three income sources, compute discrepancies |
| `risk_score` | Transparent, weighted risk score (0-100) |
| `decision` | Final call + human-readable justification |

## Tech stack

- **Python 3.12**
- **PostgreSQL 16** — applicant data, Plaid links, documents, verification history
- **LangGraph 1.2** — agent orchestration
- **Plaid Sandbox** (`plaid-python`) — real bank data integration
- **FastAPI + uvicorn** — API and UI serving
- **pdfplumber + fpdf2** — document generation and parsing
- **Docker Compose** — containerized deployment

## Data sources

- **Real:** 9,578 historical loan records (income, FICO, DTI, revolving
  balance, actual repayment outcome) from a public LendingClub-derived
  dataset.
- **Synthetic (deliberately, and clearly marked as such):** applicant
  identity (names/employers — the real dataset strips these for privacy),
  Plaid bank transaction data (Plaid Sandbox, per-applicant, seeded
  variance from stated income), and pay stub documents (same approach).

See [`docs/01-scoping.md`](docs/01-scoping.md) for the full reasoning.

## Getting started

### Prerequisites

- Docker Desktop
- Python 3.12
- A free [Plaid Sandbox](https://dashboard.plaid.com/signup) account
  (`client_id` + Sandbox `secret`, no approval wait required)

### Setup

```bash
git clone https://github.com/RajGupte/Crosscheck.git
cd Crosscheck

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file:

```
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=crosscheck
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

PLAID_CLIENT_ID=your_client_id_here
PLAID_SECRET=your_sandbox_secret_here
PLAID_ENV=sandbox
```

Start the stack and load the real dataset:

```bash
docker compose up -d
python app/db/load_lendingclub.py     # loads all 9,578 real historical records
```

Open **http://localhost:8000/** in a browser.

### API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Liveness + DB connectivity check |
| `POST` | `/applications/{id}/verify` | Run the full pipeline for an applicant |
| `GET` | `/applications/{id}/history` | Past verification runs for an applicant |
| `GET` | `/` | Web UI |
| `GET` | `/docs` | Auto-generated interactive API docs (Swagger) |

```bash
curl -X POST http://localhost:8000/applications/1/verify
```

## Evaluation

Run the eval harness against real applicants, scored against known ground
truth (synthetic discrepancies we deliberately injected):

```bash
python -m app.eval.run_eval --n 40
```

**Results (n=40):** Precision 1.0, Recall 1.0, F1 1.0 — 40/40 correct
decisions, 100% document extraction success, 100% Plaid signal success.

An independent sanity check against *real* historical loan outcomes
(`not_fully_paid`, which the agent never sees during scoring) is also
included:

```bash
python -m app.eval.historical_correlation
```

**Important caveat:** the n=40 eval is validation of the *mechanism*
(does the pipeline correctly detect discrepancies it's given), not proof
of real-world predictive accuracy — the ground truth and the risk score
both derive from the same synthetic signal. See
[`docs/02-trade-offs.md`](docs/02-trade-offs.md) for the full, honest
explanation.

## Project structure

```
crosscheck/
├── app/
│   ├── agent/
│   │   ├── nodes/              # the six pipeline steps
│   │   ├── graph.py            # LangGraph wiring
│   │   ├── state.py            # shared pipeline state
│   │   ├── income_estimator.py # recurring-deposit heuristic
│   │   ├── plaid_client.py     # Plaid Sandbox integration
│   │   └── variance.py         # shared synthetic-data variance logic
│   ├── api/
│   │   ├── main.py             # FastAPI app
│   │   └── static/index.html   # web UI
│   ├── db/
│   │   ├── init.sql            # schema
│   │   ├── db.py               # connection helper
│   │   └── load_lendingclub.py # real dataset loader
│   ├── documents/
│   │   ├── generate_pay_stub.py
│   │   └── parse_pay_stub.py
│   └── eval/
│       ├── run_eval.py
│       └── historical_correlation.py
├── data/                       # gitignored: raw CSV + generated PDFs
├── docker/Dockerfile
├── docker-compose.yml
├── docs/                       # scoping, trade-offs, incidents, standardization
└── requirements.txt
```

## Documentation

- [`docs/01-scoping.md`](docs/01-scoping.md) — the problem, why this
  vertical, what's in/out of scope
- [`docs/02-trade-offs.md`](docs/02-trade-offs.md) — real decisions made
  and the reasoning behind each
- [`docs/03-incidents.md`](docs/03-incidents.md) — every real bug hit
  during the build and how it was diagnosed/fixed
- [`docs/04-standardization.md`](docs/04-standardization.md) — what would
  need to change to run this for real customers at scale

## Known limitations

- Single-tenant, no auth on the API
- Risk-score weights are a reasoned heuristic, not a calibrated model
- Synchronous `/verify` endpoint (10-40s response time due to Plaid's
  retry-until-ready pattern)
- Document parsing handles machine-readable PDF text, not scanned images
- Plaid access tokens stored unencrypted (fine for Sandbox; would need
  encryption at rest for anything real)

Full detail on each, and what fixing them would take, in
[`docs/04-standardization.md`](docs/04-standardization.md).
