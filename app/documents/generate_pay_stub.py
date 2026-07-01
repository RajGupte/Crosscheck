"""
Generates a synthetic pay stub PDF for a given applicant.

DESIGN DECISIONS (worth understanding, not just accepting):

1. INCOME VARIANCE: the pay stub's gross income is NOT always identical to
   the applicant's stated_annual_income. Real pay stubs sometimes disagree
   with what someone wrote on a loan application (a stale stub, a recent
   raise, honest rounding, or genuine misrepresentation). We seed a
   reproducible variance per applicant so document-parsing is a real third
   signal to cross-check, not just a restatement of column 1. Most
   applicants get a small variance (+/-5%); a deliberate subset get a
   larger variance (10-30% under) to simulate the "stated income doesn't
   match reality" case Crosscheck exists to catch.

2. LABEL VARIATION: real pay stub formats differ by payroll provider
   (ADP, Gusto, Paychex, in-house systems all format differently). We
   randomly (but reproducibly) pick from a few realistic label variants
   per applicant, so the parser we build next has to handle genuine
   format variety -- not a single hardcoded layout.

3. The generator does NOT write the "ground truth" income into the
   database. The whole point is that the agent has to extract it from the
   PDF the way a human underwriter would. We return the ground truth from
   this function so we (or the eval harness later) can check the parser's
   accuracy against it -- but that value is not stored anywhere the parser
   itself could see.
"""

import os
import random

from fpdf import FPDF

from app.db.db import get_conn

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "documents")

GROSS_LABELS = ["Gross Pay", "Gross Earnings", "Total Gross"]
NET_LABELS = ["Net Pay", "Take-Home Pay", "Net Amount"]
EMPLOYER_LABELS = ["Employer", "Company", "Pay From"]


def _get_applicant(application_id: int) -> dict:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT applicant_name, stated_employer, stated_annual_income FROM loan_applications WHERE application_id = %s",
        (application_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row is None:
        raise ValueError(f"No application found with id {application_id}")
    return {"name": row[0], "employer": row[1], "stated_income": float(row[2])}


def generate_pay_stub(application_id: int) -> dict:
    applicant = _get_applicant(application_id)
    rng = random.Random(application_id)  # seeded -> reproducible per applicant

    if rng.random() < 0.25:
        variance = rng.uniform(0.65, 0.85)
    else:
        variance = rng.uniform(0.95, 1.05)

    document_annual_income = round(applicant["stated_income"] * variance, 2)
    pay_periods_per_year = 26
    gross_per_period = round(document_annual_income / pay_periods_per_year, 2)
    tax_rate = 0.22
    net_per_period = round(gross_per_period * (1 - tax_rate), 2)

    gross_label = rng.choice(GROSS_LABELS)
    net_label = rng.choice(NET_LABELS)
    employer_label = rng.choice(EMPLOYER_LABELS)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "EARNINGS STATEMENT", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.ln(4)

    pdf.cell(0, 8, f"{employer_label}: {applicant['employer']}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, f"Employee: {applicant['name']}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, "Pay Period: Biweekly", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, f"{gross_label}: ${gross_per_period:,.2f}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Federal/State Tax Withholding: ${round(gross_per_period * tax_rate, 2):,.2f}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, f"{net_label}: ${net_per_period:,.2f}", new_x="LMARGIN", new_y="NEXT")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    file_path = os.path.join(OUTPUT_DIR, f"pay_stub_{application_id}.pdf")
    pdf.output(file_path)

    return {
        "file_path": os.path.abspath(file_path),
        "ground_truth_document_annual_income": document_annual_income,
        "ground_truth_employer": applicant["employer"],
        "stated_income": applicant["stated_income"],
        "variance_applied": round(variance, 3),
    }


if __name__ == "__main__":
    import sys

    app_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    result = generate_pay_stub(app_id)
    print(result)
