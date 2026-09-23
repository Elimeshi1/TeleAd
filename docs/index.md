# telead

telead is a Python library for the [Telegram Ads API](https://ads.telegram.org/docs/api) — the API behind [ads.telegram.org](https://ads.telegram.org), where sponsored messages are bought for channels, bots and search. It is one method per API method, with typed results, local validation, idempotency keys, retries and pagination on top.
{ .lead }

```python
from telead import Client, InputAdTargetChannels

client = Client("<ACCESS_TOKEN>")

ad = client.create_ad(
    title="Autumn launch",
    text="Everything you need to know about the launch, in one channel.",
    promote_url="https://t.me/mychannel",
    cpm=2.5,
    placement="channel_post",
    target=InputAdTargetChannels(channel_ids=["@somechannel", "@anotherchannel"]),
    initial_budget=50,
)
print(ad.ad_id, ad.status)          # 1234 in_review
```

That is a live ad, funded and on its way to review.

## Installation

```bash
pip install telead
```

Python 3.9 or newer. The only runtime dependency is `requests`. Upgrade with `pip install -U telead`; releases are listed on [PyPI](https://pypi.org/project/telead/).

## Two things that shape everything

**Money is in the account's currency.** An account is denominated in Euros, Grams (TON) or Telegram Stars, fixed when it is created. Every CPM, budget and amount you send or read is in that currency — there is no conversion anywhere. [Currencies](concepts.md#4-currencies).

**Channels and bots are named by `@username`.** A numeric id works only after this account has looked that channel or bot up by username; before that the API answers `CHANNEL_ID_UNKNOWN`. [Resolving channels and bots](targeting.md#resolving-channels-and-bots).

## How this documentation is organized

<div class="sections" markdown>

### Start

- [Getting started](getting-started.md) — get a token, make your first call, create your first ad
- [How it works](concepts.md) — requests, accounts, currencies, idempotency, pagination
- [Questions and answers](faq.md) — review, minimum CPMs, agencies, rate limits

### Guides

- [Creating ads](ads.md) — create, edit, pause, schedule, submit for review, delete
- [Targeting](targeting.md) — channels, users, bots and search
- [Photos and videos](media.md) — media in ads, and the website photo
- [Budgets and accounts](budgets.md) — ad budgets, related accounts, transfers, transactions
- [Stats and reports](stats.md) — per-interval stats and monthly reports
- [Retargeting audiences](audiences.md) — audiences from phone numbers
- [Pixel and conversions](pixel.md) — the Pixel Tag and conversion events

### Reference

- [`Client`](client.md) — every method
- [Targets and schedules](inputs.md) — what you send: `InputAdTarget*`, `InputAdSchedule`
- [Models](models.md) — what you get back: `Ad`, `Account`, `AdStatItem`, …
- [Errors](errors.md) — the exception tree, error codes, retries
- [Limits and formats](limits.md) — every cap, enumeration and file format

### Practice

- [Recipes](recipes.md) — agencies, automatic top-ups, bulk edits, reports
- [Testing](testing.md) — testing your code without touching the network

</div>

---

telead is an independent library built against the Telegram Ads API as documented on September 18, 2026. It is not affiliated with or endorsed by Telegram.
