"""Node 1 of 6: pull the applicant's stated financial data (source 1) from
Postgres. This is the starting point every other node builds on."""

from app.agent.state import CrosscheckState
from app.db.db import get_conn


def fetch_application(state: CrosscheckState) -> dict:
    application_id = state["application_id"]

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT applicant_name, stated_employer, stated_annual_income, fico, dti
        FROM loan_applications
        WHERE application_id = %s
        """,
        (application_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if row is None:
        return {"errors": [f"No application found with id {application_id}"]}

    applicant_name, stated_employer, stated_income, fico, dti = row
    return {
        "applicant_name": applicant_name,
        "stated_employer": stated_employer,
        "stated_income": float(stated_income),
        "fico": fico,
        "dti": float(dti),
    }
