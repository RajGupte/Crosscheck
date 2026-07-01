"""Node 5 of 6: turn the crosscheck facts into a single risk score (0-100,
higher = riskier).

DESIGN NOTE: the weights below (50% income discrepancy, 30% credit score,
20% debt-to-income) are a starting heuristic, not a calibrated model. A
real version of this would tune these weights against actual outcome data
(e.g. the not_fully_paid column we have in loan_applications from the real
historical dataset) rather than picking round numbers. That calibration
work is out of scope for this project's v1, and is called out explicitly
in docs/trade-offs.md as a known next step."""

from app.agent.state import CrosscheckState

INCOME_DISCREPANCY_WEIGHT = 0.5
CREDIT_SCORE_WEIGHT = 0.3
DTI_WEIGHT = 0.2


def _income_discrepancy_risk(discrepancies: dict) -> float:
    """0-100: how much the stated income disagrees with the other sources."""
    diffs = [
        abs(d)
        for d in [discrepancies.get("stated_vs_plaid_pct"), discrepancies.get("stated_vs_document_pct")]
        if d is not None
    ]
    if not diffs:
        return 70.0
    worst = max(diffs)
    return min(worst / 30 * 100, 100.0)


def _credit_score_risk(fico: int) -> float:
    """0-100: lower FICO = higher risk. FICO ranges roughly 300-850."""
    if fico is None:
        return 50.0
    return max(0.0, min(100.0, (750 - fico) / (750 - 500) * 100))


def _dti_risk(dti: float) -> float:
    """0-100: higher debt-to-income ratio = higher risk."""
    if dti is None:
        return 50.0
    return max(0.0, min(100.0, dti / 40 * 100))


def risk_score(state: CrosscheckState) -> dict:
    discrepancies = state.get("discrepancies", {})

    income_risk = _income_discrepancy_risk(discrepancies)
    credit_risk = _credit_score_risk(state.get("fico"))
    dti_risk = _dti_risk(state.get("dti"))

    total = (
        income_risk * INCOME_DISCREPANCY_WEIGHT
        + credit_risk * CREDIT_SCORE_WEIGHT
        + dti_risk * DTI_WEIGHT
    )

    return {
        "risk_score": round(total, 1),
        "risk_breakdown": {
            "income_discrepancy_risk": round(income_risk, 1),
            "credit_score_risk": round(credit_risk, 1),
            "dti_risk": round(dti_risk, 1),
            "weights": {
                "income_discrepancy": INCOME_DISCREPANCY_WEIGHT,
                "credit_score": CREDIT_SCORE_WEIGHT,
                "dti": DTI_WEIGHT,
            },
        },
    }
