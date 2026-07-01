"""
Shared state passed between every node in the Crosscheck LangGraph pipeline.

LangGraph nodes each receive the full state and return a dict of the fields
they're updating; LangGraph merges that into the running state. This
TypedDict is the single source of truth for what fields exist and what they
mean, so every node file can be read without needing to trace through the
whole graph to understand its inputs/outputs.
"""

from typing import Optional, TypedDict


class CrosscheckState(TypedDict, total=False):
    # input
    application_id: int

    # populated by fetch_application
    applicant_name: str
    stated_employer: str
    stated_income: float
    fico: int
    dti: float

    # populated by fetch_plaid
    plaid_estimated_income: float
    plaid_confidence: str
    plaid_evidence: list

    # populated by parse_documents
    document_extracted_income: Optional[float]
    document_extracted_employer: Optional[str]
    document_confidence: float

    # populated by crosscheck
    discrepancies: dict

    # populated by risk_score
    risk_score: float
    risk_breakdown: dict

    # populated by decision
    decision: str  # "verified" | "flagged" | "needs_review"
    justification: str

    # any node can append here instead of crashing the whole run
    errors: list
