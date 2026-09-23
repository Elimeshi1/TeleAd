# Limits and formats

Every cap the API documents, and where the library checks it. All of these live in `telead.limits`.

## Ads

| Field | Limit | Constant |
|---|---|---|
| `title` | 1–128 **bytes** (UTF-8) | `AD_TITLE_MAX_BYTES` |
| `text` | 1–160 characters | `AD_TEXT_MAX` |
| `promote_url` | 1–256 characters | `PROMOTE_URL_MAX` |
| `website_name` | 1–40 characters | `WEBSITE_NAME_MAX` |
| `additional_info` | 0–64 characters | `ADDITIONAL_INFO_MAX` |
| `impression_frequency` | 1–4 per user per day | `IMPRESSION_FREQUENCY_RANGE` |
| `activate_date`, `deactivate_date` | future, ≤ 365 days ahead, rounded to the minute | `SCHEDULE_DAYS_AHEAD_MAX` |
| `getAdsList` `limit` | 0–100 | `ADS_LIST_LIMIT_MAX` |

A Hebrew, Arabic or Cyrillic character takes two bytes in UTF-8, so a `title` in those scripts holds about 64 characters.

## Enumerations

| | Values | Constant |
|---|---|---|
| `placement` | `channel_post`, `bot_banner`, `search_result`, `video_banner` | `PLACEMENTS` |
| `button` | `subscribe`, `view`, `read`, `learn_more`, `download`, `open`, `sign_up`, `buy`, `order`, `play`, `try`, `leave_request` | `BUTTONS` |
| `Ad.status` | `stopped`, `ready_for_review`, `in_review`, `declined`, `active`, `on_hold` | `AD_STATUSES` |
| `Ad.action_type` | `join`, `start_bot`, `launch_miniapp`, `send_message`, `page_view`, `landing_view` and the pixel event types | `ACTION_TYPES` |
| pixel event `type` | `page_view`, `add_to_cart`, `add_to_wishlist`, `customize_product`, `initiate_checkout`, `add_payment_info`, `purchase`, `contact`, `lead`, `schedule`, `complete_registration`, `submit_application`, `start_trial`, `subscribe`, `view_content`, `search`, `find_location`, `donate`, `custom` | `PIXEL_EVENT_TYPES` |
| `device` | `ios`, `android`, `mobile`, `desktop` | `DEVICES` |
| target `type` | `channels`, `users`, `bots`, `search` | `TARGET_TYPES` |
| `TransactionStatus.status` | `in_progress`, `failed`, `completed` | `TRANSACTION_STATUSES` |

## Targeting

| | Limit |
|---|---|
| `language_codes` | 8 |
| `country_codes` | 8 — exactly 1 with `location_ids` |
| `location_ids` | 20 |
| topics, included + excluded | 20 |
| channels, included + excluded | 100 |
| `bot_ids` | 100 |
| `audience_ids`, `exclude_audience_ids` | 4 each, 10 together |
| `search_queries` | 10 |

In `TARGET_LIMITS`.

## Schedules

| | |
|---|---|
| `week_hours_mask` | exactly 7 values, each 0–16,777,215 (`SCHEDULE_MASK_MAX`) |
| `timezone` | one of 40 offsets — `SCHEDULE_TIMEZONES`, [listed here](inputs.md#accepted-time-zones) |

## Uploads

| Method | Formats | Size | Checked by the API only |
|---|---|---|---|
| `uploadAdPhoto` | JPEG, PNG | 5 MB | ≥ 640 px wide, 16:9 |
| `uploadAdVideo` | MP4 | 20 MB | ≥ 640 px wide, 16:9, 3–60 s |
| `uploadWebsitePhoto` | JPEG, PNG | 1 MB | ≥ 150 × 150 px |

In `UPLOAD_LIMITS`.

## Stats

| | |
|---|---|
| `interval` | `300` or `86400` seconds (`STAT_INTERVALS`) |
| period | ≤ 1000 intervals (`STAT_MAX_POINTS`) |
| report `year` | 2021–2100 (`REPORT_YEAR_RANGE`) |
| report `month` | 1–12 |

## Audiences and pixel events

| | |
|---|---|
| audience `title` | 1–64 characters on create, 1–64 bytes on edit (`AUDIENCE_TITLE_MAX`) |
| phones per call | 10,000 (`AUDIENCE_PHONES_PER_CALL`) |
| phones per audience | 1,000,000 (`AUDIENCE_PHONES_MAX`) |
| pixel event `title` | 1–64 characters on create, 1–64 bytes on edit (`PIXEL_EVENT_TITLE_MAX`) |

## Accounts

| Field | Limit |
|---|---|
| `title` | 1–128 characters |
| `full_name` | 1–256 |
| `email` | 1–64 |
| `country`, `city` | 1–128 |
| `legal_name` | 0–256 |

In `ACCOUNT_FIELD_LIMITS`.

## Currencies

| Code | Name | CPM and budget precision | Amount precision |
|---|---|---|---|
| `EUR` | Euros | 2 | 5 |
| `TON` | Grams | 2 | 5 |
| `XTR` | Telegram Stars | 0 | 3 |

`CURRENCIES[code]` has `round_cpm()` and `round_amount()`.

## Idempotency

| | |
|---|---|
| key length | ≤ 128 characters (`IDEMPOTENCY_KEY_MAX`) |
| kept for | 24 hours |
| methods | `createAccount`, `increaseAccountBudget`, `decreaseAccountBudget`, `createAd`, `increaseAdBudget`, `decreaseAdBudget`, `createAudience`, `createPixel`, `createPixelEvent` (`IDEMPOTENT_METHODS`) |

## Rate limits

The Telegram Ads API documentation does not publish rate limits. The client handles one if it occurs; see [Errors → Retries](errors.md#retries).
