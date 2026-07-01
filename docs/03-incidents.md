# Crosscheck — What Broke, and How It Was Fixed

This is a real log of things that went wrong during the build, in
roughly chronological order. Nothing here is hypothetical — every item
was actually hit, actually diagnosed, and actually fixed (or explicitly
documented as an accepted limitation), with the fix verified against real
output before moving on.

## 1. An AI-assisted first pass scaffolded a schema for data we didn't have

**What happened:** an earlier scaffolding pass (via a coding assistant)
generated a Postgres schema (`emp_title`, `grade`, `sub_grade`, `zip_code`,
`fico_range_low/high`, etc.) matching the *full* multi-gigabyte LendingClub
Kaggle export — a dataset that requires a Kaggle login and was never
actually downloaded. The real dataset in hand was a simplified, 14-column,
publicly-hosted CSV with none of those columns.

**How it was caught:** by reading the actual downloaded CSV's header row
side-by-side with the proposed schema before running anything, rather than
trusting a summary that claimed the schema was "verified."

**Fix:** rebuilt the schema from scratch to match the actual dataset,
explicitly documenting in `init.sql` which columns are real historical
data vs. synthetically generated.

## 2. A bash brace-expansion typo silently created the wrong directory

**What happened:** `mkdir -p /path/{app/agent/nodes,app/db,...}` was run
in an environment where the shell didn't expand the brace syntax,
silently creating a literal directory named `{app` instead of the
intended nested structure.

**How it was caught:** by listing the directory tree immediately after
and noticing the malformed `{app` entry, rather than assuming the command
succeeded because it returned no error.

**Fix:** removed the bad directory and recreated the structure with
explicit `mkdir -p` calls per path.

## 3. `ModuleNotFoundError` from running scripts as files instead of modules

**What happened:** running `python app/agent/link_plaid_to_application.py`
directly failed with `ModuleNotFoundError: No module named 'app'`, because
Python only adds the *script's own directory* to its import path when run
that way — not the project root.

**Fix:** added `__init__.py` files to every `app/` subpackage and switched
to running scripts as modules (`python -m app.agent.link_plaid_to_application`),
which correctly adds the project root to the path.

## 4. Git author identity mismatch (investigated, not just assumed benign)

**What happened:** commits were being authored under a different GitHub
account (`RajD2k`) than the intended personal account (`RajGupte`), traced
to a stale global `git config user.email` left over from another context.

**How it was handled:** rather than assuming this was fine, actually
inspected the local git config, the commit author metadata, and the
relevant macOS Keychain entries to confirm this was an owned account (not
a credential leak) before concluding it was safe to leave as-is for a
low-stakes public repo.

## 5. A `zsh` history-expansion near-miss

**What happened:** a Python one-liner containing `{t['name']!r}` (a
legitimate Python f-string repr specifier) was pasted into a `zsh`
terminal. `zsh` interpreted the `!r` as a **history-expansion trigger**
and silently substituted in an unrelated prior command from shell history
(in this case, an old `rm -rf` invocation) before Python ever saw the
input.

**Why it didn't cause damage:** the resulting garbled text was invalid
Python syntax, so `python3 -c` correctly refused to execute it and raised
a `SyntaxError` instead of running anything.

**Fix / lesson:** avoided `!` in inline shell-quoted Python from then on
(used `repr()` explicitly instead of the `!r` format spec) to eliminate
the risk entirely, rather than relying on it failing safely next time.

## 6. Every applicant showed identical "bank-verified" income

**What happened:** the first working version of the Plaid integration
used Plaid's `user_transactions_dynamic` Sandbox test persona, which
returns a **fixed, shared transaction dataset** — not data specific to
whichever `access_token` requested it. This meant every applicant run
through the pipeline got the exact same Plaid-estimated income
($42,235.71, every time), silently defeating the entire purpose of
having a second, independent data source.

**How it was caught:** by comparing the full output of two different
applicants side-by-side and noticing the Plaid numbers were suspiciously
identical, rather than treating each individual pipeline run as
successful in isolation.

**Fix:** switched to Plaid's `user_custom` Sandbox persona with an
explicit, per-applicant configuration, seeded by `application_id`.

## 7. A fabricated Plaid schema field that doesn't exist

**What happened:** while building the fix for #6, an `inflow_model` field
was used in the custom Sandbox configuration, based on a description that
turned out to have been reconstructed from an incomplete page fetch
rather than the real Plaid API spec. `inflow_model` is not a real field.

**How it was caught:** live testing kept returning exactly one
transaction instead of the expected recurring pattern, which prompted
going back to primary sources (Plaid's own GitHub issue tracker and
example configs) rather than assuming the code was correct because it
didn't error.

**Fix:** rebuilt the custom Sandbox configuration using the real,
documented schema — an explicit `transactions` array per account, with
each deposit's date, amount, and description specified directly. This is
arguably a better design anyway: full control, no ambiguity about what
Plaid will generate.

**Lesson generalized:** an API call *succeeding* (no exception, valid
response) does not mean the *data* is correct. Two of the four Plaid-
related bugs in this log (this one and #8) produced clean, non-error
responses while still being wrong.

## 8. The first `transactions_sync` call reliably returns zero results

**What happened:** the very first live Plaid test returned `0
transactions` on the first call, which could have been mistaken for a
broken integration.

**How it was caught:** checked Plaid's own troubleshooting docs before
assuming a bug, which confirmed this is expected, documented behavior —
Plaid needs a few seconds to prepare data even in Sandbox.

**Fix:** added a retry loop with backoff around `transactions_sync`.

## 9. Custom Sandbox transactions don't reliably all appear

**What happened:** even after fix #7, requesting 4 monthly transactions
sometimes only returned 3 — one transaction (typically the oldest)
occasionally didn't come through.

**How it was caught:** by inspecting the raw returned transaction list
directly, rather than trusting the downstream income estimate alone.

**Resolution:** confirmed via Plaid's own public issue tracker that this
is known, reported behavior in their custom Sandbox users (not unique to
this project). Handled by keeping `min_occurrences=2` in the income
heuristic and requesting slightly more transactions (4) than strictly
required (2), so partial delivery still produces a usable signal.

## 10. Silent duplicate data from a multi-line command with one failing line

**What happened:** a two-command block (`TRUNCATE ...` followed by
`python app/db/load_lendingclub.py`) was run together. The `TRUNCATE`
failed (foreign-key constraint), but since the two commands weren't
chained with `&&`, the second line ran anyway — silently loading 9,578
fresh rows on top of 20 pre-existing test rows.

**How it was caught:** by explicitly checking the row count after,
rather than trusting the loader's own "Inserted N rows" success message
as proof the table was in the expected state.

**Fix:** re-ran `TRUNCATE ... CASCADE` (required, since other tables had
foreign keys into this one) followed by a clean reload, and verified the
final count matched expectations exactly.
