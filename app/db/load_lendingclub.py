"""
Loads the LendingClub-derived CSV (data/loan_data_raw.csv) into the
loan_applications table.

WHY THIS FILE LOOKS THE WAY IT DOES:
- The CSV has real financial columns but no applicant identity, so we
  generate a synthetic name + employer per row (seeded, so results are
  reproducible run to run).
- log.annual.inc in the source data is a NATURAL LOG of income (a common
  transform to make skewed income data more normal for modeling). We convert
  it back to a dollar figure with exp() so the rest of the pipeline works
  with plain dollars, which is what Plaid and documents will report in.
- credit.policy and not.fully.paid are 0/1 integers in the CSV; we cast them
  to booleans.
- The CSV uses OLD MAC-STYLE LINE ENDINGS (bare \r, not \n or \r\n).
  Python's csv module handles this fine as long as you open the file with
  newline='' (see below) -- if you drop that, rows will not split correctly.
"""

import argparse
import csv
import math
import os
from typing import Optional

import psycopg2
from dotenv import load_dotenv
from faker import Faker

load_dotenv()

fake = Faker()
Faker.seed(42)  # reproducible synthetic names across runs

CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "loan_data_raw.csv")

INSERT_SQL = """
    INSERT INTO loan_applications (
        applicant_name, stated_employer,
        credit_policy, purpose, int_rate, installment, stated_annual_income,
        dti, fico, days_with_credit_line, revolving_balance,
        revolving_utilization, inquiries_last_6mths, delinquencies_2yrs,
        public_records, not_fully_paid
    ) VALUES (
        %(applicant_name)s, %(stated_employer)s,
        %(credit_policy)s, %(purpose)s, %(int_rate)s, %(installment)s, %(stated_annual_income)s,
        %(dti)s, %(fico)s, %(days_with_credit_line)s, %(revolving_balance)s,
        %(revolving_utilization)s, %(inquiries_last_6mths)s, %(delinquencies_2yrs)s,
        %(public_records)s, %(not_fully_paid)s
    )
"""


def row_to_params(row: dict) -> dict:
    """Convert one raw CSV row (all strings) into typed params for the INSERT."""
    log_income = float(row["log.annual.inc"])
    return {
        "applicant_name": fake.name(),
        "stated_employer": fake.company(),
        "credit_policy": row["credit.policy"] == "1",
        "purpose": row["purpose"],
        "int_rate": float(row["int.rate"]),
        "installment": float(row["installment"]),
        "stated_annual_income": round(math.exp(log_income), 2),
        "dti": float(row["dti"]),
        "fico": int(row["fico"]),
        "days_with_credit_line": float(row["days.with.cr.line"]),
        "revolving_balance": float(row["revol.bal"]),
        "revolving_utilization": float(row["revol.util"]),
        "inquiries_last_6mths": int(row["inq.last.6mths"]),
        "delinquencies_2yrs": int(row["delinq.2yrs"]),
        "public_records": int(row["pub.rec"]),
        "not_fully_paid": row["not.fully.paid"] == "1",
    }


def main(limit: Optional[int]) -> None:
    conn = psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=os.environ.get("POSTGRES_PORT", "5432"),
        dbname=os.environ.get("POSTGRES_DB", "crosscheck"),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", "postgres"),
    )
    cur = conn.cursor()

    inserted = 0
    with open(CSV_PATH, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if limit is not None and inserted >= limit:
                break
            params = row_to_params(row)
            cur.execute(INSERT_SQL, params)
            inserted += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"Inserted {inserted} rows into loan_applications.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Only load the first N rows (for dev)")
    args = parser.parse_args()
    main(args.limit)
