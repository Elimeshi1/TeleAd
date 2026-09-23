# telead

[![PyPI](https://img.shields.io/pypi/v/telead?v=1)](https://pypi.org/project/telead/)
[![Python](https://img.shields.io/pypi/pyversions/telead?v=1)](https://pypi.org/project/telead/)
[![Docs](https://img.shields.io/badge/docs-elimeshi1.github.io-blue)](https://elimeshi1.github.io/TeleAd/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](https://github.com/Elimeshi1/TeleAd/blob/main/LICENSE)

A Python library for the [Telegram Ads API](https://ads.telegram.org/docs/api) (`https://promoteapi.telegram.org`).

It covers every method in the API documentation — accounts, related accounts and budget transfers, ads, uploads, stats and reports, retargeting audiences, the Pixel Tag and the targeting catalogue — and adds what you would otherwise write yourself: typed responses, automatic idempotency keys, safe retries, pagination, schedule builders and local validation against the documented caps.

```python
from telead import Client, InputAdTargetChannels

client = Client("<ACCESS_TOKEN>")

ad = client.create_ad(
    title="Autumn launch",
    text="Everything you need to know about the launch, in one channel.",
    promote_url="https://t.me/mychannel",
    cpm=2.5,
    placement="channel_post",
    target=InputAdTargetChannels(channel_ids=["@somechannel"]),
    initial_budget=50,
)
print(ad.ad_id, ad.status)
```

## Install

```bash
pip install telead
```

Python 3.9+. The only runtime dependency is `requests`. Upgrade with `pip install -U telead`; releases are listed on [PyPI](https://pypi.org/project/telead/).

## Documentation

**https://elimeshi1.github.io/TeleAd/**, built from [`docs/`](https://github.com/Elimeshi1/TeleAd/tree/main/docs) with MkDocs Material.

| | |
|---|---|
| [Getting started](https://elimeshi1.github.io/TeleAd/getting-started/) | Get a token, make a first call, create a first ad |
| [How it works](https://elimeshi1.github.io/TeleAd/concepts/) | Requests, accounts, currencies, idempotency, pagination |
| [Questions and answers](https://elimeshi1.github.io/TeleAd/faq/) | Review, minimum CPMs, agencies, rate limits |
| [Creating ads](https://elimeshi1.github.io/TeleAd/ads/) | Create, edit, pause, schedule, review, delete |
| [Targeting](https://elimeshi1.github.io/TeleAd/targeting/) | Channels, users, bots and search |
| [Photos and videos](https://elimeshi1.github.io/TeleAd/media/) | Media in ads, and the website photo |
| [Budgets and accounts](https://elimeshi1.github.io/TeleAd/budgets/) | Ad budgets, related accounts, transfers, transactions |
| [Stats and reports](https://elimeshi1.github.io/TeleAd/stats/) | Per-interval stats and monthly reports |
| [Retargeting audiences](https://elimeshi1.github.io/TeleAd/audiences/) | Audiences from phone numbers |
| [Pixel and conversions](https://elimeshi1.github.io/TeleAd/pixel/) | The Pixel Tag and conversion events |
| [Client](https://elimeshi1.github.io/TeleAd/client/) | Every method |
| [Targets and schedules](https://elimeshi1.github.io/TeleAd/inputs/) | `InputAdTarget*`, `InputAdSchedule` |
| [Models](https://elimeshi1.github.io/TeleAd/models/) | `Ad`, `Account`, `AdStatItem`, … |
| [Errors](https://elimeshi1.github.io/TeleAd/errors/) | Exception tree, error codes, retries |
| [Limits and formats](https://elimeshi1.github.io/TeleAd/limits/) | Every cap, enumeration and file format |
| [Recipes](https://elimeshi1.github.io/TeleAd/recipes/) | Agencies, top-ups, bulk edits, reports |
| [Testing](https://elimeshi1.github.io/TeleAd/testing/) | Testing your code without the network |

Build the site locally with:

```bash
pip install -r docs/requirements.txt
mkdocs serve
```

## At a glance

```python
from telead import Client, InputAdSchedule, InputAdTargetUsers

with Client(token) as client:
    # Balances are in the account's own currency: EUR, TON or XTR.
    account = client.get_current_account()

    # Every ad, page after page.
    for ad in client.iter_ads():
        print(ad.ad_id, ad.status, ad.views, ad.ctr)

    # A photo ad for German-speaking Android users, weekday office hours.
    photo = client.upload_ad_photo("banner.jpg")
    client.create_ad(
        title="DACH — Android",
        text="Die App für dein Team.",
        photo_id=photo.photo_id,
        promote_url="https://t.me/mybot",
        cpm=3,
        placement="channel_post",
        target=InputAdTargetUsers(country_codes=["DE", "AT", "CH"], device="android"),
        schedule=InputAdSchedule.weekly(
            {d: range(9, 18) for d in ("mon", "tue", "wed", "thu", "fri")}, timezone=3600),
        initial_budget=100,
    )

    # Agencies: act on a related account, move budget, wait for the transfer.
    acme = client.with_account("rel-123")
    final = client.wait_for_transaction(client.increase_account_budget("rel-123", 50))
```

Calls that move money or create things carry an idempotency key automatically, so a retry after a dropped connection never runs them twice.

## Examples

* [`examples/quickstart.py`](https://github.com/Elimeshi1/TeleAd/blob/main/examples/quickstart.py): the balance, and every ad with its numbers
* [`examples/create_channel_ad.py`](https://github.com/Elimeshi1/TeleAd/blob/main/examples/create_channel_ad.py): resolve channels, upload a photo, create a scheduled ad
* [`examples/weekly_report.py`](https://github.com/Elimeshi1/TeleAd/blob/main/examples/weekly_report.py): daily stats for every ad, as CSV
* [`examples/top_up_accounts.py`](https://github.com/Elimeshi1/TeleAd/blob/main/examples/top_up_accounts.py): top up related accounts that run low

## Tests

```bash
git clone https://github.com/Elimeshi1/TeleAd.git
cd TeleAd
pip install -U pip        # editable installs need pip 21.3 or newer
pip install -e ".[dev]"
pytest
```

## License

MIT. telead is an independent library, not affiliated with or endorsed by Telegram.
