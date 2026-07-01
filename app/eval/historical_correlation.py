"""
Independent validation check: does Crosscheck's risk_score correlate with
REAL historical loan outcomes (the not_fully_paid column from the actual
LendingClub-derived dataset)?

WHY THIS IS DIFFERENT FROM run_eval.py: that eval checks whether the agent
correctly detects discrepancies WE injected -- useful, but circular (the
ground truth and the risk score both trace back to variances we control).
This check instead compares against a REAL, independent signal: whether
that historical borrower actually defaulted, which the agent has never
seen and which has nothing to do with our synthetic Plaid/document data.

IMPORTANT CAVEAT (state this honestly in the writeup, not just here):
income-discrepancy detection and loan-default prediction are DIFFERENT
questions. A borrower can state their income accurately and still default
(job loss, medical bills, etc.), or misstate income and still repay. This
check is not "does Crosscheck predict defaults" -- it's a plausibility
check: if Crosscheck systematically flags applicants who, in the real
historical record, defaulted MORE often than applicants it verified, that's
a weak positive signal that the risk factors it uses point in a sane
direction. It is not proof of predictive accuracy, and should not be
oversold as such.

Usage:
    python -m app.eval.historical_correlation
"""

from app.db.db import get_conn


def run_historical_correlation() -> dict:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT DISTINCT ON (vr.application_id)
            vr.application_id, vr.risk_score, vr.decision, la.not_fully_paid
        FROM verification_runs vr
        JOIN loan_applications la ON la.application_id = vr.application_id
        WHERE vr.risk_score IS NOT NULL
        ORDER BY vr.application_id, vr.run_id DESC
        """
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        print("No verification_runs with a risk_score found -- run the eval harness first.")
        return {}

    defaulted = [r for r in rows if r[3]]
    paid = [r for r in rows if not r[3]]

    def avg_risk(group):
        scores = [float(r[1]) for r in group if r[1] is not None]
        return round(sum(scores) / len(scores), 1) if scores else None

    def decision_counts(group):
        counts = {}
        for r in group:
            counts[r[2]] = counts.get(r[2], 0) + 1
        return counts

    result = {
        "n_total": len(rows),
        "n_historically_defaulted": len(defaulted),
        "n_historically_paid": len(paid),
        "avg_risk_score_defaulted": avg_risk(defaulted),
        "avg_risk_score_paid": avg_risk(paid),
        "decision_distribution_defaulted": decision_counts(defaulted),
        "decision_distribution_paid": decision_counts(paid),
    }

    print("=== Historical Outcome Correlation (independent check) ===")
    print(f"Total applicants with a recorded risk_score: {result['n_total']}")
    print(f"  Historically defaulted (not_fully_paid=True): {result['n_historically_defaulted']}")
    print(f"  Historically paid in full: {result['n_historically_paid']}")
    print()
    print(f"Avg risk_score | historically DEFAULTED: {result['avg_risk_score_defaulted']}")
    print(f"Avg risk_score | historically PAID:       {result['avg_risk_score_paid']}")
    print()
    print(f"Decision distribution | historically DEFAULTED: {result['decision_distribution_defaulted']}")
    print(f"Decision distribution | historically PAID:       {result['decision_distribution_paid']}")

    if result["avg_risk_score_defaulted"] is not None and result["avg_risk_score_paid"] is not None:
        if result["avg_risk_score_defaulted"] > result["avg_risk_score_paid"]:
            print(
                "\nDirection check: applicants who historically defaulted have a HIGHER average "
                "risk_score than those who paid in full -- the expected direction, though this is "
                "a small, synthetic-data sample and not a claim of predictive accuracy."
            )
        else:
            print(
                "\nDirection check: applicants who historically defaulted do NOT have a higher "
                "average risk_score in this sample -- worth investigating, not ignoring."
            )

    return result


if __name__ == "__main__":
    run_historical_correlation()
