# Client

`Client` is one method per API method, plus the plumbing: authentication, idempotency keys, retries, local validation, pagination and typed results.

```python
from telead import Client

with Client("<ACCESS_TOKEN>") as client:
    print(client.get_current_account())
```

## Construction

```python
Client(
    token,
    account_id=None,
    base_url="https://promoteapi.telegram.org",
    timeout=30.0,
    max_retries=3,
    backoff_base=0.5,
    backoff_max=30.0,
    auto_idempotency=True,
    validate=True,
    session=None,
    user_agent=None,
)
```

| Argument | What it does |
|---|---|
| `token` | The access token. Sent as `Authorization: Bearer <token>`. |
| `account_id` | A related account to act on by default — filled into every method whose `account_id` is optional. See [`with_account`](#accounts-as-a-view). |
| `base_url` | Override the API root — useful for tests and proxies. |
| `timeout` | Read timeout in seconds. Uploads get at least 120. |
| `max_retries` | Retries after a retryable failure. See [Errors → Retries](errors.md#retries). |
| `backoff_base`, `backoff_max` | Exponential backoff bounds, in seconds. Jitter is added. |
| `auto_idempotency` | Attach a fresh idempotency key to each call of a method that supports one, reused across that call's retries. |
| `validate` | Check lengths, enumerations, targeting caps and uploads before a request leaves. |
| `session` | Bring your own `requests.Session` for connection reuse, proxies or custom TLS. |
| `user_agent` | Override the `User-Agent` header. |

## Methods

Arguments in *italics* below are optional. Every method that acts on an account also takes *`account_id`*; every method marked **K** also takes *`idempotency_key`*.

### Accounts

| Method | API method | Returns |
|---|---|---|
| `get_current_account()` | `getCurrentAccount` | [`Account`](models.md#account) |
| `get_accounts_by_id(account_ids)` | `getAccountsById` | `list[Account]` |
| `create_account(title, full_name=, email=, phone_number=, country=, city=, `*`legal_name`*`)` **K** | `createAccount` | [`AccountInfo`](models.md#accountinfo) |
| `get_account_info()` | `getAccountInfo` | `AccountInfo` |
| `edit_account_info(`*`title, full_name, email, phone_number, country, city, legal_name`*`)` | `editAccountInfo` | `AccountInfo` |
| `get_related_accounts_list(`*`offset, limit`*`)` | `getRelatedAccountsList` | [`RelatedAccountsList`](models.md#lists) |
| `iter_related_accounts(`*`page_size`*`)` | ↑ paged | `Iterator[Account]` |

### Budgets and transactions — [guide](budgets.md)

| Method | API method | Returns |
|---|---|---|
| `increase_account_budget(account_id, amount)` **K** | `increaseAccountBudget` | [`TransactionStatus`](models.md#transactionstatus) |
| `decrease_account_budget(account_id, amount)` **K** | `decreaseAccountBudget` | `TransactionStatus` |
| `get_transaction_status(transaction_id)` | `getTransactionStatus` | `TransactionStatus` |
| `wait_for_transaction(transaction, `*`timeout=60, interval=2`*`)` | ↑ polled | `TransactionStatus` |
| `get_account_transactions_list(`*`offset, limit`*`)` | `getAccountTransactionsList` | [`AccountTransactionsList`](models.md#lists) |
| `iter_account_transactions(`*`page_size`*`)` | ↑ paged | `Iterator[AccountTransaction]` |
| `increase_ad_budget(ad_id, amount, `*`return_target`*`)` **K** | `increaseAdBudget` | [`Ad`](models.md#ad) |
| `decrease_ad_budget(ad_id, amount, `*`return_target`*`)` **K** | `decreaseAdBudget` | `Ad` |
| `get_ad_transactions_list(ad_id, `*`offset, limit`*`)` | `getAdTransactionsList` | [`AdTransactionsList`](models.md#lists) |
| `iter_ad_transactions(ad_id, `*`page_size`*`)` | ↑ paged | `Iterator[AdTransaction]` |

In `increase_account_budget` and `decrease_account_budget`, `account_id` is the **related account** money moves to or from — required, and never filled in from the client.

### Ads — [guide](ads.md)

| Method | API method | Returns |
|---|---|---|
| `create_ad(title=, promote_url=, cpm=, target=, placement=, text=, …)` **K** | `createAd` | `Ad` |
| `edit_ad(ad_id, …)` | `editAd` | `Ad` |
| `pause_ad(ad_id)`, `resume_ad(ad_id)` | `editAd` | `Ad` |
| `submit_ad_for_review(ad_id, `*`return_target`*`)` | `submitAdForReview` | `Ad` |
| `delete_ad(ad_id)` | `deleteAd` | `bool` |
| `get_ad(ad_id, `*`return_target`*`)` | `getAdsById` | `Ad` or `None` |
| `get_ads_by_id(ad_ids, `*`return_target`*`)` | `getAdsById` | `list[Ad]` |
| `get_ads_list(`*`offset, limit, return_target`*`)` | `getAdsList` | [`AdList`](models.md#lists) |
| `iter_ads(`*`return_target, page_size`*`)` | ↑ paged | `Iterator[Ad]` |

### Uploads — [guide](media.md)

| Method | API method | Returns |
|---|---|---|
| `upload_ad_photo(file, `*`filename`*`)` | `uploadAdPhoto` | [`AdPhoto`](models.md#media) |
| `upload_ad_video(file, `*`filename`*`)` | `uploadAdVideo` | `AdVideo` |
| `upload_website_photo(file, `*`filename`*`)` | `uploadWebsitePhoto` | `WebsitePhoto` |

### Stats — [guide](stats.md)

| Method | API method | Returns |
|---|---|---|
| `get_ad_stats(ad_id, from_time, to_time, `*`interval=86400`*`)` | `getAdStats` | `list[`[`AdStatItem`](models.md#adstatitem)`]` |
| `get_account_stats(from_time, to_time, `*`interval=86400`*`)` | `getAccountStats` | `list[AdStatItem]` |
| `get_account_report(year, month)` | `getAccountReport` | `list[`[`AccountReportItem`](models.md#accountreportitem)`]` |

### Audiences — [guide](audiences.md)

| Method | API method | Returns |
|---|---|---|
| `create_audience(title, `*`phones`*`)` **K** | `createAudience` (+ `editAudience` past 10,000) | [`Audience`](models.md#audience) |
| `edit_audience(audience_id, `*`title, add_phones, remove_phones, reset_phones`*`)` | `editAudience` | `Audience` |
| `add_audience_phones(audience_id, phones, `*`batch_size`*`)` | `editAudience` × n | `Audience` |
| `remove_audience_phones(audience_id, phones, `*`batch_size`*`)` | `editAudience` × n | `Audience` |
| `delete_audience(audience_id)` | `deleteAudience` | `bool` |
| `get_audiences_by_id(audience_ids)` | `getAudiencesById` | `list[Audience]` |
| `get_audiences_list(`*`offset, limit`*`)` | `getAudiencesList` | [`AudiencesList`](models.md#lists) |

### Pixel — [guide](pixel.md)

| Method | API method | Returns |
|---|---|---|
| `create_pixel()` **K** | `createPixel` | [`Pixel`](models.md#pixel) |
| `get_pixel()` | `getPixel` | `Pixel` |
| `create_pixel_event(title, type)` **K** | `createPixelEvent` | [`PixelEvent`](models.md#pixelevent) |
| `edit_pixel_event(event_id, title)` | `editPixelEvent` | `PixelEvent` |
| `delete_pixel_event(event_id)` | `deletePixelEvent` | `bool` |
| `get_pixel_events_by_id(event_ids)` | `getPixelEventsById` | `list[PixelEvent]` |
| `get_pixel_events_list(`*`offset, limit`*`)` | `getPixelEventsList` | [`PixelEventsList`](models.md#lists) |

### Targeting catalogue — [guide](targeting.md)

These take no `account_id`.

| Method | API method | Returns |
|---|---|---|
| `get_target_languages_list()` | `getTargetLanguagesList` | `list[TargetLanguage]` |
| `get_target_topics_list()` | `getTargetTopicsList` | `list[TargetTopic]` |
| `get_target_countries_list()` | `getTargetCountriesList` | `list[TargetCountry]` |
| `get_target_locations_list(country_code, query, `*`offset, limit`*`)` | `getTargetLocationsList` | `TargetLocationList` |
| `iter_target_locations(country_code, query)` | ↑ paged | `Iterator[TargetLocation]` |
| `get_target_locations_by_id(location_ids)` | `getTargetLocationsById` | `list[TargetLocation]` |
| `get_target_channel(channel, `*`for_excluding`*`)` | `getTargetChannel` | [`TargetChannel`](models.md#catalogue) |
| `get_target_bot(bot)` | `getTargetBot` | `TargetBot` |

### Anything else

| Method | |
|---|---|
| `call(method, params=None, `*`files, idempotency_key`*`)` | Any method by name; returns the raw `result`. The client-wide `account_id`, idempotency keys and retries apply. |

`editAdStatus` is deprecated by the API and has no typed method; use `pause_ad` / `resume_ad`.

## Accounts, as a view

`with_account(account_id)` returns a client for the same token that acts on a related account by default:

```python
acme = client.with_account("rel-123")
acme.get_ads_list()               # sends account_id="rel-123"
acme.get_ads_list(account_id="rel-456")   # an explicit argument still wins
```

The view shares its parent's connection and settings; closing it leaves the connection open.

## Lifecycle

`Client` opens a `requests.Session` and reuses the connection. Close it when you're done — or use the context manager, which closes only a session the client created:

```python
with Client(token) as client:
    ...
```

A session you passed in is left open for you to manage.

## Threads

A `Client` is safe to share across threads: `requests.Session` is thread-safe for this usage and the client keeps no per-call state. See [Recipes → many accounts in parallel](recipes.md#many-accounts-in-parallel).

## Logging

The client logs to the `telead` logger. At `DEBUG` it notes when the API replayed an earlier result for an idempotency key.

## Turning the helpers off

The library validates before sending, because a round trip to learn that ad text is 161 characters is a slow way to find out. If you would rather see exactly what the API says:

```python
client = Client(token, validate=False, max_retries=0, auto_idempotency=False)
```
