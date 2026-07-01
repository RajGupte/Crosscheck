"""Node 2 of 6: get bank-verified income (source 2) via Plaid Sandbox.

Creates a Plaid Sandbox connection with income data SPECIFIC to this
applicant (or reuses an existing one, via the ON CONFLICT upsert -- see
plaid_items schema), pulls transactions, and runs them through the
income-estimation heuristic.

WHY create_custom_sandbox_item AND NOT create_sandbox_item: the latter uses
a fixed Plaid test persona that returns identical data for every applicant
-- we caught this while building the full pipeline (every applicant showed
the exact same Plaid-estimated income). create_custom_sandbox_item
generates data specific to each application_id instead."""

import random

from app.agent.income_estimator import estimate_annual_income
from app.agent.plaid_client import create_custom_sandbox_item, fetch_transactions, get_client
from app.agent.state import CrosscheckState
from app.db.db import get_conn


def _target_monthly_income(application_id: int, stated_income: float) -> float:
    """
    Computes a per-applicant target income for the simulated bank data, with
    a seed DELIBERATELY DIFFERENT from the pay stub generator's seed (see
    generate_pay_stub.py). This decorrelation matters: if both simulated
    signals used the same seed, they'd always agree or disagree together,
    which would make "two independent sources corroborate" meaningless --
    it would really just be one signal duplicated. With independent seeds,
    some applicants will have Plaid and document data that agree, some
    where they disagree, some where only one flags an issue -- which is a
    much more realistic (and useful) evaluation surface.
    """
    rng = random.Random(application_id * 104729 + 17)  # decorrelated from generate_pay_stub's seed
    if rng.random() < 0.3:
        variance = rng.uniform(0.55, 0.85)
    else:
        variance = rng.uniform(0.93, 1.07)
    annual_target = stated_income * variance
    return round(annual_target / 12, 2)


def fetch_plaid(state: CrosscheckState) -> dict:
    application_id = state["application_id"]
    stated_income = state.get("stated_income", 0.0)

    try:
        client = get_client()
        monthly_income = _target_monthly_income(application_id, stated_income)
        item = create_custom_sandbox_item(client, application_id, monthly_income)
    except Exception as e:  # noqa: BLE001 -- deliberately broad: any Plaid
        # failure should degrade gracefully into "no signal", not crash
        # the whole pipeline run.
        return {
            "plaid_estimated_income": 0.0,
            "plaid_confidence": "none",
            "plaid_evidence": [],
            "errors": [f"Plaid connection failed: {e}"],
        }

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO plaid_items (application_id, item_id, access_token, institution_id)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (application_id) DO UPDATE
        SET item_id = EXCLUDED.item_id,
            access_token = EXCLUDED.access_token,
            institution_id = EXCLUDED.institution_id
        """,
        (application_id, item["item_id"], item["access_token"], item["institution_id"]),
    )
    conn.commit()
    cur.close()
    conn.close()

    transactions = fetch_transactions(client, item["access_token"])
    income_result = estimate_annual_income(transactions)

    return {
        "plaid_estimated_income": income_result["estimated_annual_income"],
        "plaid_confidence": income_result["confidence"],
        "plaid_evidence": income_result["evidence"],
    }
