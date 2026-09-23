# Targets and schedules

What you send. Each class is a plain dataclass with `to_dict()` (the API's JSON shape) and `validate()` (the documented caps). The client calls both for you; anywhere it takes one of these, a `dict` in the API's shape works too.

```python
from telead import (
    InputAdTargetChannels, InputAdTargetUsers, InputAdTargetBots, InputAdTargetSearch,
    InputAdSchedule,
)
```

A channel or bot reference (`PeerRef`) is `"@username"` or a numeric id this account has already [resolved](targeting.md#resolving-channels-and-bots).

## InputAdTargetChannels

`type = "channels"`

| Field | Type | Rule |
|---|---|---|
| `language_codes` | `list[str]` | 0–8 IETF tags. Must be empty with `channel_ids`; exactly one with `topic_ids`. |
| `topic_ids` | `list[int]` | With `exclude_topic_ids`, ≤ 20 in total. Empty with `channel_ids`. |
| `exclude_topic_ids` | `list[int]` | |
| `channel_ids` | `list[PeerRef]` | With `exclude_channel_ids`, ≤ 100 in total. |
| `exclude_channel_ids` | `list[PeerRef]` | |

## InputAdTargetUsers

`type = "users"`

| Field | Type | Rule |
|---|---|---|
| `country_codes` | `list[str]` | 0–8 ISO 3166-1 alpha-2 codes. Exactly one with `location_ids`. Always sent. |
| `location_ids` | `list[int]` | 0–20, all in that country. |
| `language_codes` | `list[str]` | 0–8 IETF tags. |
| `topic_ids`, `exclude_topic_ids` | `list[int]` | ≤ 20 in total. |
| `intersect_topics` | `bool` | Require every topic. |
| `channel_ids`, `exclude_channel_ids` | `list[PeerRef]` | ≤ 100 in total. |
| `audience_ids`, `exclude_audience_ids` | `list[int]` | 0–4 each, ≤ 10 in total. |
| `device` | `str` | `ios`, `android`, `mobile` or `desktop`. |
| `exclude_political_channels` | `bool` | |
| `political_channels_only` | `bool` | Not together with the one above. |

## InputAdTargetBots

`type = "bots"`

| Field | Type | Rule |
|---|---|---|
| `bot_ids` | `list[PeerRef]` | 0–100. |

## InputAdTargetSearch

`type = "search"`

| Field | Type | Rule |
|---|---|---|
| `search_queries` | `list[str]` | Up to 10 keywords or phrases. |

## InputAdSchedule

| Field | Type | |
|---|---|---|
| `week_hours_mask` | `list[int]` | Seven 24-bit masks, **Monday first**. Bit *n* is the hour *n*:00–*n*+1:00. All zero means "any time". |
| `timezone` | `int` | Offset from UTC in **seconds**, one of `telead.limits.SCHEDULE_TIMEZONES`. Required unless `use_viewer_timezone`. |
| `use_viewer_timezone` | `bool` | Each viewer's own time zone. Users targeting only. |

Build one from hours:

| Constructor | |
|---|---|
| `InputAdSchedule.every_day(hours, timezone=…, use_viewer_timezone=False)` | the same hours all week |
| `InputAdSchedule.weekly({day: hours, …}, timezone=…)` | `day` is `0`–`6` or `"mon"`…`"sun"` (full names work too); days left out show nothing |

```python
schedule = InputAdSchedule.weekly({"mon": range(9, 18), "fri": range(9, 14)}, timezone=7200)
schedule.hours(0)          # [9, 10, …, 17]
schedule.to_dict()         # {"week_hours_mask": [261632, 0, 0, 0, 15872, 0, 0], "timezone": 7200}
```

Pass `schedule=False` to `edit_ad` to remove a schedule.

## Accepted time zones

Offsets in hours: −12, −11, −10, −9½, −9, −8, −7, −6, −5, −4, −3½, −3, −2½, −2, −1, 0, +1, +2, +3, +3½, +4, +4½, +5, +5½, +5¾, +6, +6½, +7, +8, +8¾, +9, +9½, +10, +10½, +11, +12, +12¾, +13, +13¾, +14. Multiply by 3600 for the value to send.
