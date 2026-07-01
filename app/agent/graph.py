"""
The Crosscheck agent pipeline: six nodes, run in sequence, that pull an
applicant's stated data, bank-verified income (Plaid), and document-
extracted income, cross-check them against each other, compute a risk
score, and produce a decision with justification.

Usage:
    python -m app.agent.graph <application_id>
"""

import json
import sys

from langgraph.graph import END, StateGraph

from app.agent.nodes.crosscheck import crosscheck
from app.agent.nodes.decision import decision
from app.agent.nodes.fetch_application import fetch_application
from app.agent.nodes.fetch_plaid import fetch_plaid
from app.agent.nodes.parse_documents import parse_documents
from app.agent.nodes.risk_score import risk_score
from app.agent.state import CrosscheckState
from app.db.db import get_conn


def build_graph():
    graph = StateGraph(CrosscheckState)

    graph.add_node("fetch_application", fetch_application)
    graph.add_node("fetch_plaid", fetch_plaid)
    graph.add_node("parse_documents", parse_documents)
    graph.add_node("crosscheck", crosscheck)
    graph.add_node("risk_score", risk_score)
    graph.add_node("decision", decision)

    graph.set_entry_point("fetch_application")
    graph.add_edge("fetch_application", "fetch_plaid")
    graph.add_edge("fetch_plaid", "parse_documents")
    graph.add_edge("parse_documents", "crosscheck")
    graph.add_edge("crosscheck", "risk_score")
    graph.add_edge("risk_score", "decision")
    graph.add_edge("decision", END)

    return graph.compile()


def run_and_record(application_id: int) -> dict:
    app_graph = build_graph()
    result = app_graph.invoke({"application_id": application_id})

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO verification_runs (
            application_id, stated_income, plaid_estimated_income,
            document_extracted_income, discrepancies, risk_score,
            decision, justification
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            application_id,
            result.get("stated_income"),
            result.get("plaid_estimated_income"),
            result.get("document_extracted_income"),
            json.dumps(result.get("discrepancies", {})),
            result.get("risk_score"),
            result.get("decision"),
            result.get("justification"),
        ),
    )
    conn.commit()
    cur.close()
    conn.close()

    return result


if __name__ == "__main__":
    app_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    final_state = run_and_record(app_id)
    print(json.dumps(final_state, indent=2, default=str))
