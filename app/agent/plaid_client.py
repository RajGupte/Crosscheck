"""
Reusable Plaid Sandbox helper functions. Wraps the connect / create-item /
fetch-transactions logic we already verified works, so it isn't duplicated
across scripts.
"""

import os
import time

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
    """
    Creates a fake Plaid Sandbox bank connection and returns the access_token
    + item_id needed for subsequent API calls.

    Defaults to Plaid's documented "user_transactions_dynamic" test user,
    which is seeded with realistic recurring transaction patterns (as
    opposed to the fully-random default test data, which may or may not
    contain a detectable income pattern -- we verified this difference
    firsthand while building this).
    """
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


def fetch_transactions(client: plaid_api.PlaidApi, access_token: str, max_attempts: int = 6) -> list:
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
            break
        time.sleep(3)
    return [{"date": str(t["date"]), "name": t["name"], "amount": t["amount"]} for t in transactions]
