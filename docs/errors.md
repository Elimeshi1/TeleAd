# Errors

Every failure raises a subclass of `TeleadError`.

```
TeleadError
├── ValidationError              the library stopped the request locally (also a ValueError)
├── TransportError               no HTTP response at all — network failure, timeout
└── APIError                     an error response from the API
    ├── AuthenticationError          ACCESS_TOKEN_REQUIRED, ACCESS_TOKEN_INVALID
    ├── InvalidRequestError          *_REQUIRED, *_INVALID, *_TOO_LONG, …
    │   └── UnknownPeerError         CHANNEL_ID_UNKNOWN, BOT_ID_UNKNOWN
    ├── NotEnoughBudgetError         NOT_ENOUGH_BUDGET
    ├── IdempotencyMismatchError     IDEMPOTENT_PARAM_MISMATCH
    ├── RequestInProgressError       IDEMPOTENT_REQUEST_IN_PROGRESS
    ├── RateLimitError               HTTP 429, FLOOD_WAIT_<n>
    └── ServerError                  HTTP 5xx, or a body that is not the API's JSON
```

```python
from telead import APIError, UnknownPeerError, ValidationError

try:
    client.create_ad(...)
except ValidationError as exc:
    ...        # never left the process: text too long, bad placement, too many topics
except UnknownPeerError:
    ...        # use "@username" instead of a numeric id
except APIError as exc:
    print(exc.code)        # e.g. "AD_TITLE_REQUIRED"
```

## What an APIError carries

| Attribute | |
|---|---|
| `code` | the API's `error` string — **the value to branch on** |
| `method` | the API method that failed, e.g. `createAd` |
| `status` | the HTTP status — `200` for ordinary API errors |
| `raw` | the full response body |

The API reports failures as HTTP 200 with `{"ok": false, "error": "<CODE>"}`; the status only differs for transport-level problems. `str(exc)` reads like `AD_TITLE_REQUIRED [method=createAd, http=200]`.

## How codes map to classes

The API documentation names a handful of codes; the rest follow a naming pattern. The mapping, in order:

1. Known codes — the ones in the tree above.
2. `FLOOD_WAIT_<n>` or HTTP 429 → `RateLimitError`, with `retry_after` set to *n* or the `Retry-After` header.
3. Any other `ACCESS_TOKEN_*` → `AuthenticationError`.
4. Codes ending in `_REQUIRED`, `_INVALID`, `_TOO_LONG`, `_TOO_SHORT`, `_EMPTY` or `_TOO_MANY` → `InvalidRequestError`.
5. Anything else → `APIError`, or `ServerError` for HTTP 5xx.

A response that is not the API's JSON at all — a gateway error page, an empty body — raises `ServerError` with `code` set to `HTTP_<status>`.

## Codes worth knowing

| Code | Class | Meaning |
|---|---|---|
| `ACCESS_TOKEN_REQUIRED` | `AuthenticationError` | No token was sent. |
| `ACCESS_TOKEN_INVALID` | `AuthenticationError` | The token is wrong or no longer valid. |
| `CHANNEL_ID_UNKNOWN` | `UnknownPeerError` | A numeric channel id this account never resolved by username. [More](targeting.md#resolving-channels-and-bots). |
| `BOT_ID_UNKNOWN` | `UnknownPeerError` | The same, for a bot. |
| `NOT_ENOUGH_BUDGET` | `NotEnoughBudgetError` | The source budget cannot cover the amount. Also appears as `TransactionStatus.error` on a failed transfer. |
| `IDEMPOTENT_PARAM_MISMATCH` | `IdempotencyMismatchError` | A key was reused with different parameters. |
| `IDEMPOTENT_REQUEST_IN_PROGRESS` | `RequestInProgressError` | The first request with this key is still running. Retried automatically. |
| `AD_TITLE_REQUIRED` | `InvalidRequestError` | The example error the API docs give. |

## Retries

The client retries automatically, with exponential backoff and jitter, up to `max_retries` (default 3). Whether a failure is retried depends on the failure **and** on whether repeating the call could do something twice:

| The call is… | Examples | Retried after network errors and 5xx? |
|---|---|---|
| a read | every `get*` method | ✅ |
| an edit that sets absolute values | `editAd`, `editAudience`, `editAccountInfo`, `editPixelEvent` | ✅ |
| a method with an idempotency key | `createAd`, `increaseAdBudget`, `increaseAccountBudget`, `createAudience`, … | ✅ — the API replays the first result |
| any other write | `deleteAd`, `submitAdForReview`, `deleteAudience`, `deletePixelEvent`, uploads | ❌ — it may already have happened |

On top of that:

| Failure | Retried? |
|---|---|
| `RateLimitError` | ✅ always — the request was refused before it ran |
| `RequestInProgressError` | ✅ — the repeat waits for, then replays, the first result |
| Any other `APIError` | ❌ — a repeat fails the same way |
| `ValidationError` | never sent |

A rate limit with a known wait (`Retry-After`, `FLOOD_WAIT_<n>`) waits exactly that long, capped by `backoff_max`. Without one, the backoff starts at 5 seconds.

```python
client = Client(token, max_retries=0)                 # handle everything yourself
client = Client(token, max_retries=6, backoff_max=60) # patient batch job
```

!!! note "Idempotency keys last 24 hours"
    The automatic key covers one call and its retries. To make a *repeat run of your program* safe, pass your own `idempotency_key` derived from your records. See [idempotency](concepts.md#6-idempotency).

## Local validation

`ValidationError` means the request never left the process. It is raised for, among others: ad text over 160 characters; a title over 128 UTF-8 bytes; an unknown `placement`, `button`, `device` or pixel event type; `photo_id` together with `video_id`; `impression_frequency` outside 1–4; too many languages, topics, channels, bots, audiences or search queries; `topic_ids` without exactly one language; `location_ids` without exactly one country; a malformed schedule or time zone; a stats period over 1000 intervals; an upload of the wrong format or size; more than 10,000 phone numbers in one `edit_audience` call.

Turn it off to see exactly what the API says:

```python
client = Client(token, validate=False)
```
