"""
Reusable Plaid Sandbox helper functions. Wraps the connect / create-item /
fetch-transactions logic we already verified works, so it isn't duplicated
across scripts.
"""

import json
import os
import time
from datetime import date

import plaid
from dotenv import load_dotenv
from plaid.api import plaid_api
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.products import Products
from plaid.model.sandbox_public_token_create_request import SandboxPublicTokenCreateRequest
from plaid.model.sandbox_public_token_create_request_options import (
    SandboxPublicTokenCreateRequestOptions,
)
from plaid.model.transactions_sync_request import TransactionsSyncRequest

load_dotenv()


def get_client() -> plaid_api.PlaidApi:
    configuration = plaid.Configuration(
        host=plaid.Environment.Sandbox,
        api_key={
            "clientId": os.environ["PLAID_CLIENT_ID"],
            "secret": os.environ["PLAID_SECRET"],
        },
    )
    return plaid_api.PlaidApi(plaid.ApiClient(configuration))


def create_sandbox_item(
    client: plaid_api.PlaidApi,
    institution_id: str = "ins_109508",
    override_username: str = "user_transactions_dynamic",
    override_password: str = "anypassword",
) -> dict:
    """Kept for reference/testing -- uses a FIXED shared test persona.
    Prefer create_custom_sandbox_item for per-applicant data."""
    options = SandboxPublicTokenCreateRequestOptions(
        override_username=override_username,
        override_password=override_password,
    )
    pt_response = client.sandbox_public_token_create(
        SandboxPublicTokenCreateRequest(
            institution_id=institution_id,
            initial_products=[Products("transactions")],
            options=options,
        )
    )
    exchange_response = client.item_public_token_exchange(
        ItemPublicTokenExchangeRequest(public_token=pt_response["public_token"])
    )
    return {
        "access_token": exchange_response["access_token"],
        "item_id": exchange_response["item_id"],
        "institution_id": institution_id,
    }


def create_custom_sandbox_item(
    client: plaid_api.PlaidApi,
    application_id: int,
    monthly_income: float,
    institution_id: str = "ins_109508",
    months: int = 4,
) -> dict:
    """
    Creates a Plaid Sandbox connection with CUSTOM, per-applicant recurring
    monthly income, using Plaid's "user_custom" test persona with an
    explicit override_accounts[].transactions[] list (see
    plaid.com/docs/sandbox/user-custom/ and
    github.com/plaid/sandbox-custom-users/issues/19 for the real schema --
    an earlier version of this function used a fabricated "inflow_model"
    field that does not actually exist in Plaid's spec; this version
    specifies each deposit transaction explicitly instead, which is both
    correct and gives us full control over dates/amounts).

    SIGN CONVENTION: per Plaid's own example data, a negative "amount" in
    the override schema means money coming IN (a credit/deposit) -- same
    convention as transactions returned by transactions_sync. So a payroll
    deposit of $X is specified as amount=-X here.
    """
    today = date.today()
    transactions = []
    for i in range(months):
        month = today.month - i
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        txn_date = date(year, month, 1).isoformat()
        transactions.append(
            {
                "date_transacted": txn_date,
                "date_posted": txn_date,
                "amount": -monthly_income,
                "description": "DIRECT DEP PAYROLL",
                "currency": "USD",
            }
        )

    config = {
        "override_accounts": [
            {
                "type": "depository",
                "subtype": "checking",
                "starting_balance": 5000,
                "meta": {"name": f"Crosscheck Applicant {application_id} Checking"},
                "transactions": transactions,
            }
        ]
    }
    options = SandboxPublicTokenCreateRequestOptions(
        override_username="user_custom",
        override_password=json.dumps(config),
    )
    pt_response = client.sandbox_public_token_create(
        SandboxPublicTokenCreateRequest(
            institution_id=institution_id,
            initial_products=[Products("transactions")],
            options=options,
        )
    )
    exchange_response = client.item_public_token_exchange(
        ItemPublicTokenExchangeRequest(public_token=pt_response["public_token"])
    )
    return {
        "access_token": exchange_response["access_token"],
        "item_id": exchange_response["item_id"],
        "institution_id": institution_id,
    }


def fetch_transactions(client: plaid_api.PlaidApi, access_token: str, max_attempts: int = 10, wait_seconds: int = 4) -> list:
    """
    Pulls transactions for an access_token, retrying if the first call
    returns empty (a well-documented Plaid behavior -- the first sync call
    often returns 0 transactions while Plaid finishes preparing the data).
    """
    transactions: list = []
    for attempt in range(max_attempts):
        sync_response = client.transactions_sync(TransactionsSyncRequest(access_token=access_token))
        transactions = sync_response["added"]
        if transactions:
            print(f"    (got {len(transactions)} transactions after {attempt + 1} attempt(s))")
            break
        print(f"    (attempt {attempt + 1}/{max_attempts}: 0 transactions yet, waiting {wait_seconds}s...)")
        time.sleep(wait_seconds)
    return [{"date": str(t["date"]), "name": t["name"], "amount": t["amount"]} for t in transactions]
