"""Node 6 of 6: turn the risk score into a decision, with a justification
an underwriter can actually read and act on -- not just a bare number."""

from app.agent.state import CrosscheckState

RISK_SCORE_FLAG_THRESHOLD = 60
RISK_SCORE_REVIEW_THRESHOLD = 30


def decision(state: CrosscheckState) -> dict:
    score = state.get("risk_score", 100)
    discrepancies = state.get("discrepancies", {})
    plaid_confidence = discrepancies.get("plaid_confidence")
    document_confidence = discrepancies.get("document_confidence") or 0

    weak_evidence = plaid_confidence in (None, "none") or document_confidence < 0.5

    if weak_evidence:
        final_decision = "needs_review"
        reason = "insufficient corroborating evidence from bank data and/or documents"
    elif score >= RISK_SCORE_FLAG_THRESHOLD:
        final_decision = "flagged"
        reason = "high risk score driven by income discrepancy and/or credit factors"
    elif score >= RISK_SCORE_REVIEW_THRESHOLD:
        final_decision = "needs_review"
        reason = "moderate risk score warrants a second look"
    else:
        final_decision = "verified"
        reason = "stated income is consistent with bank and document data, credit factors are acceptable"

    justification = (
        f"{state.get('applicant_name', 'Applicant')}: risk_score={score}/100 ({reason}). "
        f"Stated income ${state.get('stated_income'):,.2f} vs. "
        f"Plaid-estimated ${state.get('plaid_estimated_income', 0):,.2f} "
        f"({discrepancies.get('stated_vs_plaid_pct')}% diff, confidence={plaid_confidence}), "
        f"document-extracted "
        f"${state.get('document_extracted_income') or 0:,.2f} "
        f"({discrepancies.get('stated_vs_document_pct')}% diff, confidence={document_confidence}). "
        f"FICO={state.get('fico')}, DTI={state.get('dti')}. "
        f"Employer name match: {discrepancies.get('employer_name_match')}."
    )

    return {"decision": final_decision, "justification": justification}
