# How it works

Seven ideas cover the whole API. The rest of the docs assume them.

## 1. Every call is one method name

There are no resources or verbs — each call is a method name appended to the root:

```
https://promoteapi.telegram.org/getAdsList
https://promoteapi.telegram.org/createAd
```

The client maps each to a Python method: `getAdsList` → `get_ads_list`, `createAd` → `create_ad`. It always uses `POST` with a JSON body (the API also accepts `GET`, query strings and form bodies; they are equivalent). Uploads use `multipart/form-data`.

For a method the platform adds after this release, use the raw call:

```python
result = client.call("someNewMethod", {"ad_id": 42})
```

## 2. Every response has `ok`

```json
{"ok": true,  "result": {"ad_id": 42, "title": "…"}}
{"ok": false, "error": "AD_TITLE_REQUIRED"}
```

**Errors arrive with HTTP status 200.** The `error` string is what identifies them. The client returns `result`, parsed into a [model](models.md), or raises an [`APIError`](errors.md) whose `code` is the `error` string.

## 3. Accounts: current, main and related

A token belongs to one account — the **current account**. An agency's main account can create **related accounts** (one per client, say) and move budget to and from them.

Most methods act on the current account unless you pass `account_id`:

```python
client.get_ads_list()                         # the current account's ads
client.get_ads_list(account_id="rel-123")     # a related account's ads
```

To work on one related account for a while, make a view of the client instead of repeating the argument:

```python
acme = client.with_account("rel-123")
acme.get_ads_list()
acme.create_ad(...)
```

`with_account` shares the connection. See [Budgets and accounts](budgets.md).

## 4. Currencies

An account is denominated in one currency, set when it is created and never changed:

| Currency | Code | CPM and budget precision | Amount precision |
|---|---|---|---|
| Euros | `EUR` | 2 decimals | 5 decimals |
| Grams | `TON` | 2 decimals | 5 decimals |
| Telegram Stars | `XTR` | 0 decimals | 3 decimals |

Every monetary field — CPMs, budgets, amounts moved, money spent — is in the account's currency, and every object that has one carries a `currency` field. The API rounds what you send to the precision above; `telead.CURRENCIES` lets you do the same first:

```python
from telead import CURRENCIES

account = client.get_current_account()
rules = account.currency_info                 # CURRENCIES[account.currency]
cpm = rules.round_cpm(2.456)                  # 2.46 in EUR/TON, 2 in XTR
```

## 5. Channels and bots by username

Targeting names channels and bots either as `"@username"` or by numeric id. **A numeric id only works once this account has resolved it by username.** Before that, the API answers `CHANNEL_ID_UNKNOWN` or `BOT_ID_UNKNOWN`.

So use usernames. When you need the id — to store it, say — resolve the username once:

```python
channel = client.get_target_channel("@durov")
channel.channel_id        # usable as a numeric id from now on, by this account
```

## 6. Idempotency

Several methods move money or create things: `createAd`, `increaseAdBudget`, `increaseAccountBudget`, `createAudience` and others. Sending one twice — because the connection dropped before the answer arrived, say — would create two ads or move the money twice.

The API prevents that with **idempotency keys**. A request carrying a key the API has seen in the last 24 hours gets the first response replayed instead of running again.

**The client adds a key to every call of these methods by default** and reuses it when it retries that call. You can pass your own — useful when your *program* might repeat the operation, for example after a crash:

```python
client.increase_account_budget("rel-123", 100, idempotency_key=f"invoice-{invoice.id}")
```

Keys are up to 128 characters. Reusing a key with different parameters raises `IdempotencyMismatchError`. The full list of methods is `telead.limits.IDEMPOTENT_METHODS`; the rules are in [Errors → Retries](errors.md#retries).

## 7. Lists and pages

List methods return one page, plus what you need for the next:

* `getAdsList`, the transaction lists and `getTargetLocationsList` return a `next_offset` — pass it back as `offset`.
* `getRelatedAccountsList`, `getAudiencesList` and `getPixelEventsList` return everything unless you pass `limit`.

The `iter_*` methods follow the pages for you:

```python
for ad in client.iter_ads():
    ...
for transaction in client.iter_account_transactions():
    ...
```

| Iterator | Pages over |
|---|---|
| `iter_ads()` | `getAdsList` |
| `iter_ad_transactions(ad_id)` | `getAdTransactionsList` |
| `iter_account_transactions()` | `getAccountTransactionsList` |
| `iter_related_accounts()` | `getRelatedAccountsList` |
| `iter_target_locations(country_code, query)` | `getTargetLocationsList` |
