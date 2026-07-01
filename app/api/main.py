"""
Minimal API wrapper around the Crosscheck agent pipeline.

This turns Crosscheck from "a script you run" into "a service you can
call" -- the shape that actually makes sense to deploy and hit from a
real client (a loan-origination system, an internal review tool, etc.),
rather than something someone has to SSH in and run manually.

Endpoints:
    GET  /health                                -> liveness + DB check
    POST /applications/{application_id}/verify   -> run the full pipeline
    GET  /applications/{application_id}/history   -> past verification runs
"""

import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app.agent.graph import run_and_record
from app.db.db import get_conn

app = FastAPI(title="Crosscheck", description="Income verification agent for loan underwriting")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/health")
def health():
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        db_ok = True
    except Exception:  # noqa: BLE001 -- health check should report, not crash
        db_ok = False

    return {"status": "ok" if db_ok else "degraded", "database": "connected" if db_ok else "unreachable"}


@app.post("/applications/{application_id}/verify")
def verify(application_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM loan_applications WHERE application_id = %s", (application_id,))
    exists = cur.fetchone() is not None
    cur.close()
    conn.close()

    if not exists:
        raise HTTPException(status_code=404, detail=f"No application found with id {application_id}")

    try:
        result = run_and_record(application_id)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Pipeline run failed: {e}") from e

    return result


@app.get("/applications/{application_id}/history")
def history(application_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT run_id, stated_income, plaid_estimated_income, document_extracted_income,
               risk_score, decision, justification, created_at
        FROM verification_runs
        WHERE application_id = %s
        ORDER BY run_id DESC
        """,
        (application_id,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        raise HTTPException(status_code=404, detail=f"No verification runs found for application {application_id}")

    return [
        {
            "run_id": r[0],
            "stated_income": float(r[1]) if r[1] is not None else None,
            "plaid_estimated_income": float(r[2]) if r[2] is not None else None,
            "document_extracted_income": float(r[3]) if r[3] is not None else None,
            "risk_score": float(r[4]) if r[4] is not None else None,
            "decision": r[5],
            "justification": r[6],
            "created_at": r[7].isoformat() if r[7] else None,
        }
        for r in rows
    ]
