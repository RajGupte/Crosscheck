"""
Extracts employer name and gross income from a pay stub PDF.

This has to handle real label variation (different payroll systems phrase
things differently -- see generate_pay_stub.py for the variants we
generate). The regex patterns below match ALL known variants -- a
production system would need this list to keep growing as it encounters
real-world pay stub formats it hasn't seen. This is the "ugly 80%" the
project brief is about: there's no way to handle every format on day one.
"""

import re

import pdfplumber

GROSS_PATTERN = re.compile(
    r"(?:Gross Pay|Gross Earnings|Total Gross)\s*:\s*\$?([\d,]+\.\d{2})",
    re.IGNORECASE,
)
EMPLOYER_PATTERN = re.compile(
    r"(?:Employer|Company|Pay From)\s*:\s*(.+)",
    re.IGNORECASE,
)

PAY_PERIODS_PER_YEAR = {
    "biweekly": 26,
    "weekly": 52,
    "monthly": 12,
    "semimonthly": 24,
}
PERIOD_PATTERN = re.compile(r"Pay Period\s*:\s*(\w+)", re.IGNORECASE)


def parse_pay_stub(file_path: str) -> dict:
    with pdfplumber.open(file_path) as pdf:
        text = pdf.pages[0].extract_text() or ""

    gross_match = GROSS_PATTERN.search(text)
    employer_match = EMPLOYER_PATTERN.search(text)
    period_match = PERIOD_PATTERN.search(text)

    if gross_match is None:
        return {
            "extracted_income": None,
            "extracted_employer": None,
            "confidence": 0.0,
            "raw_text": text,
            "note": "Could not find a recognized gross pay label in this document.",
        }

    gross_per_period = float(gross_match.group(1).replace(",", ""))

    period_key = period_match.group(1).lower() if period_match else "biweekly"
    periods_per_year = PAY_PERIODS_PER_YEAR.get(period_key, 26)
    annual_income = round(gross_per_period * periods_per_year, 2)

    employer = employer_match.group(1).strip() if employer_match else None

    confidence = 0.95 if period_match else 0.7

    return {
        "extracted_income": annual_income,
        "extracted_employer": employer,
        "confidence": confidence,
        "raw_text": text,
    }


if __name__ == "__main__":
    import sys

    file_path = sys.argv[1]
    result = parse_pay_stub(file_path)
    print(result)
