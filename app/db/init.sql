-- Crosscheck database schema
--
-- IMPORTANT CONTEXT FOR WHOEVER READS THIS LATER:
-- loan_applications is seeded from a real, public LendingClub-derived dataset
-- (9,578 historical loan records). The FINANCIAL columns (income, fico, dti,
-- revolving balance, repayment outcome, etc.) are REAL data from real past
-- borrowers.
--
-- However, the public dataset does NOT include applicant identity (no name,
-- no employer) -- that was stripped before release for privacy. Since
-- Crosscheck's job is to verify identity-linked documents against bank data,
-- we synthetically generate applicant_name and stated_employer per row when
-- we load the data. Those two columns are clearly marked below as synthetic.
-- Every other column in loan_applications is real historical data.

CREATE TABLE IF NOT EXISTS loan_applications (
    application_id      BIGSERIAL PRIMARY KEY,

    -- SYNTHETIC (generated at load time -- not in the original dataset)
    applicant_name       TEXT NOT NULL,
    stated_employer       TEXT NOT NULL,

    -- REAL (from the LendingClub-derived dataset, column names in parens)
    credit_policy         BOOLEAN,        -- credit.policy
    purpose                TEXT,           -- purpose
    int_rate                NUMERIC(6, 4),  -- int.rate
    installment              NUMERIC(10, 2), -- installment
    stated_annual_income      NUMERIC(14, 2), -- derived: exp(log.annual.inc)
    dti                        NUMERIC(6, 2),  -- dti
    fico                        INT,            -- fico
    days_with_credit_line        NUMERIC(10, 2), -- days.with.cr.line
    revolving_balance             NUMERIC(14, 2), -- revol.bal
    revolving_utilization           NUMERIC(6, 2),  -- revol.util
    inquiries_last_6mths              INT,            -- inq.last.6mths
    delinquencies_2yrs                 INT,            -- delinq.2yrs
    public_records                       INT,            -- pub.rec
    not_fully_paid                        BOOLEAN,        -- not.fully.paid (historical outcome)

    created_at                             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_loan_applications_purpose ON loan_applications (purpose);

-- Source (2): Plaid sandbox items, one per applicant, holding the access
-- token needed to pull real (sandbox) bank transaction data.
CREATE TABLE IF NOT EXISTS plaid_items (
    plaid_item_id    BIGSERIAL PRIMARY KEY,
    application_id    BIGINT NOT NULL REFERENCES loan_applications (application_id),
    item_id            TEXT NOT NULL,
    access_token        TEXT NOT NULL,  -- NOTE: plaintext for this demo; a real
                                         -- system must encrypt this at rest.
    institution_id        TEXT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (application_id)
);

-- Source (3): documents (pay stubs, bank statements) submitted by the
-- applicant, and what the agent extracted from them.
CREATE TABLE IF NOT EXISTS documents (
    document_id             BIGSERIAL PRIMARY KEY,
    application_id            BIGINT NOT NULL REFERENCES loan_applications (application_id),
    doc_type                    TEXT NOT NULL CHECK (doc_type IN ('pay_stub', 'bank_statement')),
    file_path                     TEXT NOT NULL,
    extracted_income                NUMERIC(14, 2),
    extracted_employer                TEXT,
    extraction_confidence                NUMERIC(4, 3),
    raw_extraction                         JSONB,
    created_at                              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_documents_application_id ON documents (application_id);

-- Agent output: one row per Crosscheck run against an application.
CREATE TABLE IF NOT EXISTS verification_runs (
    run_id                      BIGSERIAL PRIMARY KEY,
    application_id                BIGINT NOT NULL REFERENCES loan_applications (application_id),
    stated_income                    NUMERIC(14, 2),
    plaid_estimated_income              NUMERIC(14, 2),
    document_extracted_income             NUMERIC(14, 2),
    discrepancies                          JSONB,
    risk_score                              NUMERIC(5, 2),
    decision                                 TEXT CHECK (decision IN ('verified', 'flagged', 'needs_review')),
    justification                             TEXT,
    created_at                                 TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_verification_runs_application_id ON verification_runs (application_id);
