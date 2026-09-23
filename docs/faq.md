# Questions and answers

## Where do I get a token?

At [ads.telegram.org/account/api](https://ads.telegram.org/account/api), logged in with the account that owns the ads. See [Getting started](getting-started.md#2-get-an-access-token).

## Why does creating an ad not start it straight away?

Every ad is reviewed. An ad with money in its budget is submitted automatically when it is created or edited; its status goes to `in_review`, then `active` or `declined`.

An ad with an empty budget is not submitted automatically. It may sit in `ready_for_review` — then call `submit_ad_for_review` once it has a budget:

```python
if ad.needs_review_submission:
    client.submit_ad_for_review(ad.ad_id)
```

## What is the minimum CPM?

It depends on the account's currency and on the ad's other parameters. A CPM below the minimum is rejected with an [`APIError`](errors.md); there is no method that returns the minimum up front.

Separately from the minimum, some features need a higher CPM to actually be shown. On average, according to the API docs: +50–80 % for a photo, +70–100 % for a video, +30 % for the channel's or bot's userpic.

## I get `CHANNEL_ID_UNKNOWN` for a channel id I know is right

Numeric channel and bot ids can only be used after this account has resolved that channel by username. Use `"@username"` — or resolve it once with `client.get_target_channel("@username")`, after which the numeric id works too. [Details](targeting.md#resolving-channels-and-bots).

## I get `MAIN_ACCOUNT_REQUIRED`, `RETARGETING_DISABLED` or `ACCESS_DENIED`

These raise [`PermissionDeniedError`](errors.md): the account cannot use that part of the API at all, so fixing the parameters or retrying will not help.

* `MAIN_ACCOUNT_REQUIRED` — the method is for [main (agency) accounts](concepts.md#3-accounts-current-main-and-related), and this token belongs to an ordinary advertiser account. Related accounts, transfers between accounts and `getTransactionStatus` are out of reach; everything about your own ads works.
* `RETARGETING_DISABLED` — retargeting audiences are not enabled for the account.
* `ACCESS_DENIED` — the account has no access to the feature, for example the Pixel Tag.

To find out what a token can do, call a read method from each area and see which ones raise it.

## Can one token manage several accounts?

Yes, if they are related accounts of the token's account. Pass `account_id=` to any method, or make a view:

```python
acme = client.with_account("rel-123")
acme.iter_ads()
```

[Budgets and accounts](budgets.md) covers creating related accounts and funding them.

## Can I lower an ad's budget, or delete it, while it runs?

No. Both `decrease_ad_budget` and `delete_ad` need the ad to have been **inactive for at least 10 minutes**. Pause it, wait, then withdraw or delete:

```python
client.pause_ad(ad_id)
# … at least ten minutes later …
client.decrease_ad_budget(ad_id, remaining)
client.delete_ad(ad_id)
```

## What are the rate limits?

The Telegram Ads API documentation does not publish any. If the API does rate-limit a call — with HTTP 429 or a `FLOOD_WAIT_<seconds>` error — the client waits and retries it, and raises [`RateLimitError`](errors.md) only after `max_retries`. For bulk jobs, keep requests sequential rather than parallel.

## Is it safe to retry a call that failed with a network error?

For reads, edits and every method that takes an idempotency key: yes, and the client already does. For `deleteAd`, `submitAdForReview`, `deleteAudience` and `deletePixelEvent` the client does not retry after a dropped connection, because it cannot know whether the first attempt ran. [Errors → Retries](errors.md#retries).

## Is there an async client?

No — `Client` is synchronous and thread-safe. For parallel reports, run calls in a thread pool; see [Recipes](recipes.md#many-accounts-in-parallel).

## `editAdStatus` is missing

It is deprecated in favour of `editAd` with `is_paused`. Use `client.pause_ad(ad_id)` and `client.resume_ad(ad_id)`. The raw `client.call("editAdStatus", {...})` still reaches it if you need it.

## Should I send phone numbers or hashes to an audience?

Either. The API accepts phone numbers or their SHA-256 hashes, and the library passes them through unchanged. The docs do not specify how a number is normalized before hashing, so if you hash, test a small audience first and check its `size`. [Retargeting audiences](audiences.md).

## Why is `ad.target` `None`?

Target settings are returned only when you ask for them: pass `return_target=True` to `create_ad`, `edit_ad`, `get_ads_by_id`, `get_ads_list` and the budget methods.
