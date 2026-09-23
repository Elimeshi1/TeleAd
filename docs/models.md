# Models

What you get back. Every model is a frozen dataclass built from the API's JSON, with one addition: `raw`, the dict it was parsed from, so a field the platform adds later is reachable before the library knows about it.

```python
ad = client.get_ad(42)
ad.raw.get("some_new_field")
```

Optional fields the API left out are `None` (or `False`/`[]` for flags and lists). Times are Unix seconds, as the API sends them, with `datetime` properties alongside. Money is a `float` in the object's `currency`; `currency_info` gives that currency's [precision rules](concepts.md#4-currencies).

## Account

| Field | |
|---|---|
| `account_id` | `str` |
| `title` | `str` |
| `currency` | `EUR`, `TON` or `XTR` |
| `spent_budget` | spent so far |
| `remaining_budget` | free to spend |
| `ads_budget` | sitting in ads' budgets |

## AccountInfo

`account_id`, `title`, `full_name`, `email`, `phone_number`, `country`, `city`, `legal_name` (optional).

## TransactionStatus

| Field | |
|---|---|
| `transaction_id` | `str` |
| `status` | `in_progress`, `failed` or `completed` — also `is_pending`, `is_failed`, `is_completed` |
| `currency`, `amount` | negative when money was withdrawn from the related account |
| `main_account`, `related_account` | [`Account`](#account) |
| `error` | why it failed, e.g. `NOT_ENOUGH_BUDGET` |

## Ad

| Field | |
|---|---|
| `ad_id` | `int` |
| `title`, `text`, `promote_url` | |
| `placement` | `channel_post`, `bot_banner`, `search_result` or `video_banner` |
| `status` | `stopped`, `ready_for_review`, `in_review`, `declined`, `active` or `on_hold` |
| `decline_reason` | [`DeclineReason`](#declinereason), when declined |
| `target` | an [`AdTarget*`](#targets) — only with `return_target=True` |
| `photo`, `video` | [`AdPhoto`, `AdVideo`](#media) |
| `website_name`, `website_photo` | `str`, [`WebsitePhoto`](#media) |
| `button`, `conversion_event_id`, `additional_info` | |
| `show_userpic` | `bool` |
| `impression_frequency` | views per user per day; `None` means once |
| `currency`, `cpm` | |
| `spent_budget`, `remaining_budget` | |
| `daily_spent_budget`, `daily_budget_limit` | when a daily limit is set |
| `views`, `clicks`, `opens` | `clicks` and `opens` may be `None` |
| `actions`, `action_type` | conversions and what counts as one ([details](stats.md#actions-and-conversions)) |
| `is_paused`, `activate_date`, `deactivate_date` | |
| `schedule` | [`AdSchedule`](#adschedule) |
| `created_date` | |

Properties: `created_at`, `activate_at`, `deactivate_at` (`datetime`), `is_active`, `is_declined`, `needs_review_submission`, `ctr` (`clicks / views`, or `None`).

## DeclineReason

`text` — a short reason; `description_html` — the full explanation, as HTML.

## AdSchedule

`week_hours_mask` (seven masks, Monday first), `timezone` (seconds from UTC), `use_viewer_timezone`. `hours(weekday)` lists the hours set on a day; `is_set` is `False` when every mask is zero. Build one to send with [`InputAdSchedule`](inputs.md#inputadschedule).

## Media

| Model | Fields |
|---|---|
| `AdPhoto` | `photo_id`, `photo_url` |
| `AdVideo` | `video_id`, `video_url` |
| `WebsitePhoto` | `photo_id`, `photo_url` |

Ids belong to the account that uploaded them.

## Targets

`Ad.target` is one of these, chosen by its `type`:

| Model | `type` | Fields |
|---|---|---|
| `AdTargetChannels` | `channels` | `languages`, `topics`, `exclude_topics`, `channels`, `exclude_channels` |
| `AdTargetUsers` | `users` | `countries`, `locations`, `languages`, `topics`, `intersect_topics`, `exclude_topics`, `channels`, `exclude_channels`, `audiences`, `exclude_audiences`, `device`, `exclude_political_channels`, `political_channels_only` |
| `AdTargetBots` | `bots` | `bots` |
| `AdTargetSearch` | `search` | `search_queries` |

Lists hold full [catalogue](#catalogue) objects — names, not just ids. A type the library does not know yet arrives as `UnknownObject` with `type` and `raw`.

## AdStatItem

`from_time`, `to_time` (with `start`, `end` as `datetime`), `views`, `opens`, `clicks`, `actions`, `currency`, `spent_budget`.

## AccountReportItem

`ad_id`, `ad_title`, `ad_is_deleted`, `views`, `opens`, `clicks`, `actions`, `currency`, `spent_budget`.

## Transactions

| Model | Fields |
|---|---|
| `AccountTransaction` | `peer`, `date` (`when` as `datetime`), `currency`, `amount` |
| `AdTransaction` | `peer`, `date` (`when`), `currency`, `amount` |

The peer models are listed in [Budgets → Transactions](budgets.md#transactions).

## Audience

`audience_id`, `title`, `size` (approximate; `50` means fewer than 100), `ads_count`, `created_date`, `updated_date` (with `created_at`, `updated_at`).

## Pixel

`pixel_id`, `code_snippet` — the base snippet for every page.

## PixelEvent

`event_id`, `title`, `type`, `status` (`active`/`inactive`), `ads_count`, `created_date`, `last_triggered_date`, `auto_created`, `code_snippet` (with `created_at`, `last_triggered_at`).

## Catalogue

| Model | Fields |
|---|---|
| `TargetLanguage` | `language_code`, `name` |
| `TargetTopic` | `topic_id`, `name` |
| `TargetCountry` | `country_code`, `name` |
| `TargetLocation` | `location_id`, `name`, `country_code`, `region` |
| `TargetChannel` | `channel_id`, `title`, `username`, `photo_url` |
| `TargetBot` | `bot_id`, `title`, `username`, `photo_url` |

`channel_id` and `bot_id` can exceed 32 bits.

## Lists

Paged results. Each one iterates over its items and has a length, so `for ad in client.get_ads_list():` works.

| Model | Items | `next_offset` |
|---|---|---|
| `AdList` | `ads` | ✓ |
| `AccountTransactionsList` | `transactions` | ✓ |
| `AdTransactionsList` | `transactions` | ✓ |
| `TargetLocationList` | `locations` | ✓ |
| `RelatedAccountsList` | `accounts` | — |
| `AudiencesList` | `audiences` | — |
| `PixelEventsList` | `events` | — |

All have `total_count`.
