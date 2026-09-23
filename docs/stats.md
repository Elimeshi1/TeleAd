# Stats and reports

`getAdStats`, `getAccountStats`, `getAccountReport`.

## Per-interval stats

```python
from datetime import datetime, timedelta, timezone

end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
start = end - timedelta(days=7)

for item in client.get_ad_stats(42, start, end, interval=86400):
    print(item.start.date(), item.views, item.clicks, item.actions, item.spent_budget)
```

`get_account_stats(start, end, interval)` returns the same thing for the whole account.

| Argument | |
|---|---|
| `from_time` | Start, **included**. Rounded down to the start of an interval. |
| `to_time` | End, **not included**. Rounded down too. |
| `interval` | `300` (5 minutes) or `86400` (1 day). Default `86400`. |

Times are Unix seconds, `datetime` objects (naive ones are read as UTC) or `date` objects (midnight UTC). The period may cover **at most 1000 intervals** — about 3½ days at 5 minutes, or 2¾ years at one day. The library checks that before sending.

Each [`AdStatItem`](models.md#adstatitem) has:

| Field | |
|---|---|
| `from_time`, `to_time` (`start`, `end` as `datetime`) | the interval |
| `views` | impressions |
| `clicks` | clicks |
| `opens` | video opens |
| `actions` | conversions — see below |
| `spent_budget`, `currency` | money spent in the interval |

## Actions and conversions

`actions` counts the user actions the ad tracks as conversions. Which action that is depends on the ad's `action_type` — one of `join`, `start_bot`, `launch_miniapp`, `send_message`, `landing_view` or a [pixel event](pixel.md) type such as `purchase`. If an ad has no `action_type`, its `actions` is 0.

`actions` used to be called `joins`; the library reads either.

## Monthly report

A calendar month's totals, one line per ad:

```python
for line in client.get_account_report(2026, 9):
    print(line.ad_id, line.ad_title, line.views, line.clicks, line.spent_budget, line.currency)
```

`year` is 2021–2100, `month` 1–12. Lines for deleted ads have `ad_is_deleted=True`.

## Totals on the ad itself

`Ad` carries running totals, so a dashboard of current numbers needs no stats call at all:

```python
for ad in client.iter_ads():
    print(ad.title, ad.views, ad.clicks, ad.ctr, ad.spent_budget)
```

`ad.ctr` is `clicks / views`, or `None` when there are no views or the API returned no click count.

A full CSV export is in [`examples/weekly_report.py`](https://github.com/Elimeshi1/TeleAd/blob/main/examples/weekly_report.py).
