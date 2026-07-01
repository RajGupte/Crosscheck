"""Node 3 of 6: get document-extracted income (source 3).

Generates a synthetic pay stub for this applicant (reproducible per
application_id -- see generate_pay_stub.py), parses it, and records the
result in the documents table."""

import os

from app.agent.state import CrosscheckState
from app.db.db import get_conn
from app.documents.generate_pay_stub import generate_pay_stub
from app.documents.parse_pay_stub import parse_pay_stub


def parse_documents(state: CrosscheckState) -> dict:
    application_id = state["application_id"]

    gen = generate_pay_stub(application_id)
    parsed = parse_pay_stub(gen["file_path"])

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO documents (
            application_id, doc_type, file_path,
            extracted_income, extracted_employer, extraction_confidence, raw_extraction
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            application_id,
            "pay_stub",
            os.path.relpath(gen["file_path"]),
            parsed["extracted_income"],
            parsed["extracted_employer"],
            parsed["confidence"],
            None,
        ),
    )
    conn.commit()
    cur.close()
    conn.close()

    return {
        "document_extracted_income": parsed["extracted_income"],
        "document_extracted_employer": parsed["extracted_employer"],
        "document_confidence": parsed["confidence"],
    }
