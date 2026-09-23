# Getting started

This page takes you from nothing to a running ad in four steps.

## 1. Install

```bash
pip install telead
```

## 2. Get an access token

The API uses a token tied to your advertiser account.

1. Open **[ads.telegram.org/account/api](https://ads.telegram.org/account/api)** and log in with the Telegram account that owns the advertiser account.
2. Copy the **access token** shown there.
3. Keep it somewhere safe — an environment variable, a secrets manager. Anyone holding it can spend the account's budget.

```bash
export TELEGRAM_ADS_TOKEN="…"
```

!!! warning "Treat the token like a password"
    It carries full control of the account: creating ads, moving budget between accounts, deleting audiences. Never commit it, never log it, and replace it at [ads.telegram.org/account/api](https://ads.telegram.org/account/api) if it leaks.

## 3. Make a first call

```python
import os
from telead import Client

client = Client(os.environ["TELEGRAM_ADS_TOKEN"])

account = client.get_current_account()
print(account.title)
print(account.remaining_budget, account.currency)   # 120.5 TON
```

If the token is wrong you get an [`AuthenticationError`](errors.md) whose `code` is `ACCESS_TOKEN_INVALID`.

A few read-only calls to look around:

```python
for ad in client.iter_ads():
    print(ad.ad_id, ad.status, ad.title)

languages = client.get_target_languages_list()     # [TargetLanguage(language_code='en', name='English'), …]
topics = client.get_target_topics_list()
countries = client.get_target_countries_list()
```

## 4. Create an ad

An ad needs five things: an internal **title**, the **text** people see (up to 160 characters), the **link** it promotes, a **CPM** and a **target**. Give it a budget as well — an ad with no budget is not sent to review.

```python
from telead import InputAdTargetChannels

ad = client.create_ad(
    title="First ad",                                   # only you see this
    text="Daily notes on Python, in one channel.",      # the audience sees this
    promote_url="https://t.me/mychannel",
    cpm=2.5,                                            # per 1000 views, account currency
    placement="channel_post",
    target=InputAdTargetChannels(channel_ids=["@somechannel"]),
    initial_budget=20,
)

print(ad.ad_id, ad.status)       # 1234 in_review
```

The ad goes to review. When it is approved its status becomes `active` and it starts showing; if it is declined, `ad.decline_reason` says why.

```python
ad = client.get_ad(ad.ad_id)
if ad.is_declined:
    print(ad.decline_reason.text)
```

## What to read next

* [How it works](concepts.md) — the handful of ideas the rest of the docs assume.
* [Creating ads](ads.md) — photos, schedules, pausing, budgets, review.
* [Targeting](targeting.md) — the four ways to choose who sees an ad.
