"""
Standalone script to verify the Plaid Sandbox connection works end-to-end.
NOT part of the agent pipeline yet -- this is purely a connectivity test.

WHY THE RETRY LOOP EXISTS:
Plaid's own docs are explicit that the FIRST call to /transactions/sync
commonly returns zero transactions -- it takes Plaid a few seconds to
finish preparing the data, even in Sandbox. Treating that first empty
response as a failure would be a false negative, not a real bug. The
correct pattern (per Plaid's docs) is to retry with a short delay.
"""

import os
import time

import plaid
from dotenv import load_dotenv
from plaid.api import plaid_api
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.products import Products
from plaid.model.sandbox_public_token_create_request import SandboxPublicTokenCreateRequest
from plaid.model.transactions_sync_request import TransactionsSyncRequest

load_dotenv()

CLIENT_ID = os.environ["PLAID_CLIENT_ID"]
SECRET = os.environ["PLAID_SECRET"]

configuration = plaid.Configuration(
    host=plaid.Environment.Sandbox,
    api_key={"clientId": CLIENT_ID, "secret": SECRET},
)
api_client = plaid.ApiClient(configuration)
client = plaid_api.PlaidApi(api_client)

print("Creating sandbox public token...")
pt_request = SandboxPublicTokenCreateRequest(
    institution_id="ins_109508",
    initial_products=[Products("transactions")],
)
pt_response = client.sandbox_public_token_create(pt_request)
public_token = pt_response["public_token"]
print(f"  Got public_token: {public_token[:20]}...")

print("Exchanging for access_token...")
exchange_request = ItemPublicTokenExchangeRequest(public_token=public_token)
exchange_response = client.item_public_token_exchange(exchange_request)
access_token = exchange_response["access_token"]
item_id = exchange_response["item_id"]
print(f"  Got access_token: {access_token[:20]}...")
print(f"  item_id: {item_id}")

print("Fetching transactions (retrying until data is ready)...")
transactions = []
for attempt in range(6):
    sync_request = TransactionsSyncRequest(access_token=access_token)
    sync_response = client.transactions_sync(sync_request)
    transactions = sync_response["added"]
    if transactions:
        break
    print(f"  Attempt {attempt + 1}: 0 transactions yet, waiting 3s...")
    time.sleep(3)

print("\nSuccess! Retrieved", len(transactions), "transactions.")
print("\nFirst 3 transactions:")
for txn in transactions[:3]:
    print(f"  {txn['date']}  {txn['name']:<30}  ${txn['amount']}")
