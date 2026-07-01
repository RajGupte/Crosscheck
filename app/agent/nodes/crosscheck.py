"""Node 4 of 6: compare the three income sources (stated, Plaid-estimated,
document-extracted) against each other and record the discrepancies.

This node does not make a judgment call about risk or approval -- it just
computes and records the facts. Turning those facts into a risk_score is
the next node's job, and turning that into a decision is the one after
that. Keeping these separate makes each step individually inspectable."""

from app.agent.state import CrosscheckState


def _pct_diff(a: float, b: float) -> float | None:
    if a is None or b is None or a == 0:
        return None
    return round((a - b) / a * 100, 1)


def crosscheck(state: CrosscheckState) -> dict:
    stated = state.get("stated_income")
    plaid = state.get("plaid_estimated_income")
    document = state.get("document_extracted_income")

    stated_employer = (state.get("stated_employer") or "").strip().lower()
    document_employer = (state.get("document_extracted_employer") or "").strip().lower()
    employer_match = bool(stated_employer) and bool(document_employer) and stated_employer == document_employer

    discrepancies = {
        "stated_vs_plaid_pct": _pct_diff(stated, plaid),
        "stated_vs_document_pct": _pct_diff(stated, document),
        "plaid_vs_document_pct": _pct_diff(plaid, document) if document is not None else None,
        "employer_name_match": employer_match,
        "plaid_confidence": state.get("plaid_confidence"),
        "document_confidence": state.get("document_confidence"),
    }

    return {"discrepancies": discrepancies}
