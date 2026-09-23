# Creating ads

`createAd`, `editAd`, `submitAdForReview`, `deleteAd`, `getAdsById`, `getAdsList`.

## Create

```python
from telead import InputAdTargetChannels

ad = client.create_ad(
    title="Autumn launch — tech channels",
    text="Everything you need to know about the launch, in one channel.",
    promote_url="https://t.me/mychannel",
    cpm=2.5,
    placement="channel_post",
    target=InputAdTargetChannels(language_codes=["en"], topic_ids=[12, 31]),
    initial_budget=50,
)
```

### Required

| Argument | |
|---|---|
| `title` | Your internal name, 1–128 **bytes** of UTF-8. Never shown to users. |
| `text` | What people see, 1–160 characters. Required for every target type except `search`. |
| `promote_url` | The link the button opens: a channel, post, bot or website. Up to 256 characters. |
| `cpm` | Price per 1000 impressions, in the account's [currency](concepts.md#4-currencies). |
| `target` | Who sees it — one of the [four target types](targeting.md). |
| `placement` | `channel_post`, `bot_banner`, `search_result` or `video_banner`. |

!!! note "Always pass `placement`"
    The API still accepts an ad without `placement` and infers it from the target type, but its docs say that may stop working. The library does not guess it for you.

### Optional

| Argument | |
|---|---|
| `photo_id` / `video_id` | Media from [`upload_ad_photo` / `upload_ad_video`](media.md). One or the other. Channels and users targeting only. |
| `show_userpic` | Show the promoted channel's or bot's picture. |
| `impression_frequency` | Times one user may see the ad per day, 1–4. Default 1. |
| `website_name`, `website_photo_id` | For an external link: a name of 1–40 characters (required then) and a [photo](media.md#website-photo). |
| `button` | For an external link: `subscribe`, `view`, `read`, `learn_more`, `download`, `open`, `sign_up`, `buy`, `order`, `play`, `try` or `leave_request`. Omit for "Open Website". |
| `conversion_event_id` | A [pixel event](pixel.md) that counts as a conversion. External links only; cannot be changed once set. |
| `additional_info` | Up to 64 characters users can see — only if the account has a `legal_name`. Cannot be changed once set. |
| `initial_budget` | Moved from the account budget into the ad. |
| `daily_budget_limit` | Cap on spend per day; `0` means none. |
| `is_paused` | Create it on hold. |
| `activate_date`, `deactivate_date` | When to start and stop — see [Start and stop dates](#start-and-stop-dates). |
| `schedule` | Hours of the week — see [Schedules](#schedules). |
| `return_target` | Include `target` in the returned `Ad`. |
| `idempotency_key` | Your own key; one is generated otherwise. See [idempotency](concepts.md#6-idempotency). |
| `account_id` | Create it in a related account. |

The result is an [`Ad`](models.md#ad).

## Review

An ad with money in its budget is submitted for review automatically when it is created or edited. An ad without one is not; it can wait in `ready_for_review` until you submit it.

| `status` | Meaning |
|---|---|
| `ready_for_review` | Not submitted — call `submit_ad_for_review(ad_id)`. |
| `in_review` | Waiting for review. |
| `active` | Approved and running. |
| `declined` | Rejected; `decline_reason.text` and `decline_reason.description_html` say why. |
| `on_hold` | On hold — not running for now. |
| `stopped` | Stopped. |

```python
ad = client.get_ad(ad_id)
if ad.needs_review_submission:
    ad = client.submit_ad_for_review(ad_id)
elif ad.is_declined:
    print(ad.decline_reason.text)
```

## Edit

`edit_ad` changes only what you pass:

```python
client.edit_ad(ad_id, text="New copy, same link.", cpm=3.1)
```

* A new `photo_id` or `video_id` **replaces** the current media.
* `conversion_event_id` and `additional_info` **cannot be changed** once set.
* `daily_budget_limit=0` removes the daily limit; `schedule=False` removes the schedule.
* Editing an ad that has a budget sends it back to review.

## Pause and resume

```python
client.pause_ad(ad_id)            # edit_ad(ad_id, is_paused=True)
client.resume_ad(ad_id)           # edit_ad(ad_id, is_paused=False)
```

Pausing or resuming this way clears any `activate_date` and `deactivate_date`.

## Start and stop dates

`activate_date` and `deactivate_date` take Unix seconds, or a `datetime` (naive ones are treated as UTC). They are rounded to the minute, and must be in the future but no more than 365 days ahead.

```python
from datetime import datetime, timezone

client.create_ad(
    ...,
    activate_date=datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc),
    deactivate_date=datetime(2026, 11, 30, tzinfo=timezone.utc),
)
```

They interact with `is_paused`:

* `activate_date` in the future → the ad is held until then.
* `deactivate_date` alone, in the future → the ad runs until then.
* Either one set → `is_paused` is ignored.

## Schedules

A schedule limits the hours of the week an ad runs. Build one from hours rather than bitmasks:

```python
from telead import InputAdSchedule

# 09:00–18:00 every day, in UTC+3
InputAdSchedule.every_day(range(9, 18), timezone=3 * 3600)

# Weekday evenings and Saturday mornings, in UTC
InputAdSchedule.weekly(
    {"mon": range(18, 23), "tue": range(18, 23), "wed": range(18, 23),
     "thu": range(18, 23), "fri": range(18, 23), "sat": range(8, 12)},
    timezone=0,
)

# 18:00–23:00 in each viewer's own time zone — users targeting only
InputAdSchedule.every_day(range(18, 23), use_viewer_timezone=True)
```

`range(9, 18)` covers the hours starting 09:00 through 17:00, so the ad runs 09:00–18:00. The time zone must be one of the offsets the API accepts (`telead.limits.SCHEDULE_TIMEZONES`); whole hours from UTC−12 to UTC+12 are all there, plus the common half- and quarter-hour zones. See [Targets and schedules](inputs.md#inputadschedule).

To remove a schedule:

```python
client.edit_ad(ad_id, schedule=False)
```

## Read

```python
ad = client.get_ad(42)                        # one ad, or None
ads = client.get_ads_by_id([42, 43, 44])      # several
page = client.get_ads_list(limit=50)          # one page: page.ads, page.next_offset
for ad in client.iter_ads():                  # all of them
    ...
```

Add `return_target=True` to any of these to get `ad.target`.

## Delete

```python
client.delete_ad(ad_id)           # True
```

The ad must have been inactive for at least 10 minutes. To take its remaining budget back first, use [`decrease_ad_budget`](budgets.md#ad-budgets).
