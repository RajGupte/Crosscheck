"""
Links a Plaid Sandbox bank connection to a specific loan_applications row,
pulls transaction data, estimates income from it, and records the
comparison against the applicant's stated income.

WHAT THIS DOES NOT DO YET (by design -- scope for a later stage):
- Does not parse documents (source 3) -- document_extracted_income is left
  NULL for now.
- Does not compute a risk_score or decision -- those depend on document
  data too, and belong in the full agent pipeline (Stage 4), not here.
This script's only job is: prove sources (1) and (2) can be joined for a
real applicant, with the comparison stored and queryable.

Usage:
    python app/agent/link_plaid_to_application.py <application_id>
"""

import json
import sys

from app.agent.income_estimator import estimate_annual_income
from app.agent.plaid_client import create_sandbox_item, fetch_transactions, get_client
from app.db.db import get_conn


def link_and_verify(application_id: int) -> None:
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "SELECT applicant_name, stated_annual_income FROM loan_applications WHERE application_id = %s",
        (application_id,),
    )
    row = cur.fetchone()
    if row is None:
        print(f"No application found with id {application_id}")
        return
    applicant_name, stated_income = row
    print(f"Applicant: {applicant_name}")
    print(f"Stated annual income: ${stated_income}")

    client = get_client()
    print("\nCreating Plaid Sandbox connection...")
    item = create_sandbox_item(client)
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
    print(f"  Linked Plaid item_id {item['item_id']} to application {application_id}")

    print("\nFetching transactions...")
    transactions = fetch_transactions(client, item["access_token"])
    print(f"  Pulled {len(transactions)} transactions")

    income_result = estimate_annual_income(transactions)
    plaid_income = income_result["estimated_annual_income"]
    print(f"  Plaid-estimated annual income: ${plaid_income} (confidence: {income_result['confidence']})")

    discrepancy_dollars = round(float(stated_income) - plaid_income, 2)
    discrepancy_pct = (
        round(discrepancy_dollars / float(stated_income) * 100, 1) if stated_income else None
    )
    discrepancies = {
        "stated_vs_plaid_dollars": discrepancy_dollars,
        "stated_vs_plaid_pct": discrepancy_pct,
        "plaid_evidence": income_result["evidence"],
    }

    cur.execute(
        """
        INSERT INTO verification_runs (
            application_id, stated_income, plaid_estimated_income,
            document_extracted_income, discrepancies
        ) VALUES (%s, %s, %s, %s, %s)
        """,
        (application_id, stated_income, plaid_income, None, json.dumps(discrepancies)),
    )

    conn.commit()
    cur.close()
    conn.close()

    print(f"\nDiscrepancy: ${discrepancy_dollars} ({discrepancy_pct}% of stated income)")
    print("Verification run recorded.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python app/agent/link_plaid_to_application.py <application_id>")
        sys.exit(1)
    link_and_verify(int(sys.argv[1]))
