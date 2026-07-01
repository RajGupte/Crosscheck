"""
Estimates annual income from a list of Plaid transactions using a simple,
explainable heuristic: find recurring, similarly-sized deposits and
annualize them.

WHY THIS APPROACH (vs. Plaid's own Bank Income product):
Plaid's Bank Income product exists and does this more sophisticatedly, but
requires separate account approval and is billed per use in production. This
heuristic is fully transparent (you can see exactly why a number was
produced), needs no extra API access beyond what we already have, and is a
reasonable v1 -- see docs/trade-offs.md for the fuller reasoning.

PLAID SIGN CONVENTION: in Plaid's transaction data, a POSITIVE amount means
money LEAVING the account (a purchase, a payment) and a NEGATIVE amount
means money COMING IN (a deposit, a refund, a paycheck). This is the
opposite of how most people intuitively think about "positive = good."
"""

from collections import defaultdict
from datetime import date
from statistics import median
from typing import TypedDict


class Transaction(TypedDict):
    date: str  # "YYYY-MM-DD"
    name: str
    amount: float


def _parse_date(d: str) -> date:
    year, month, day = (int(x) for x in d.split("-"))
    return date(year, month, day)


def estimate_annual_income(
    transactions: list[Transaction],
    amount_tolerance_pct: float = 0.1,
    min_occurrences: int = 2,
) -> dict:
    """
    Returns a dict with the estimated annual income and the evidence used
    to compute it, so the result is always explainable, not a black box.
    """
    deposits = [t for t in transactions if t["amount"] < 0]

    groups: dict[str, list[Transaction]] = defaultdict(list)
    for t in deposits:
        groups[t["name"]].append(t)

    candidates = []
    for name, group in groups.items():
        if len(group) < min_occurrences:
            continue

        amounts = [abs(t["amount"]) for t in group]
        med = median(amounts)
        if med == 0:
            continue

        if not all(abs(a - med) / med <= amount_tolerance_pct for a in amounts):
            continue

        dates = sorted(_parse_date(t["date"]) for t in group)
        span_days = (dates[-1] - dates[0]).days
        if span_days == 0:
            continue

        occurrences_per_year = (len(group) - 1) / span_days * 365

        candidates.append(
            {
                "name": name,
                "median_amount": round(med, 2),
                "occurrences": len(group),
                "occurrences_per_year_est": round(occurrences_per_year, 1),
                "annualized_estimate": round(med * occurrences_per_year, 2),
                "dates": [t["date"] for t in group],
            }
        )

    if not candidates:
        return {
            "estimated_annual_income": 0.0,
            "confidence": "none",
            "evidence": [],
            "note": "No recurring deposit pattern found in the available transaction history.",
        }

    best = max(candidates, key=lambda c: c["annualized_estimate"])

    return {
        "estimated_annual_income": best["annualized_estimate"],
        "confidence": "medium" if best["occurrences"] >= 3 else "low",
        "evidence": [best],
        "other_candidates": [c for c in candidates if c is not best],
    }
