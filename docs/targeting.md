# Targeting

Every ad has one target, of one of four types. Pass it as an object from `telead`, or as a `dict` in the API's own shape.

| Type | Class | Shown |
|---|---|---|
| `channels` | `InputAdTargetChannels` | in chosen channels |
| `users` | `InputAdTargetUsers` | to chosen users |
| `bots` | `InputAdTargetBots` | in chosen bots |
| `search` | `InputAdTargetSearch` | in search results for chosen queries |

Pair the target with a `placement`: `channel_post`, `bot_banner`, `search_result` or `video_banner`. The API documents the placements but not which target each one allows; a combination it does not accept is rejected by `createAd` with an [`APIError`](errors.md).

Every target validates itself against the documented caps before it is sent — see [Targets and schedules](inputs.md) for the full rules.

## Channels

Three ways in, one at a time:

```python
from telead import InputAdTargetChannels

# 1. Channels in up to 8 languages
InputAdTargetChannels(language_codes=["en", "de"])

# 2. Channels on up to 20 topics, in exactly one language
InputAdTargetChannels(language_codes=["en"], topic_ids=[12, 31])

# 3. Up to 100 specific channels — no languages or topics then
InputAdTargetChannels(channel_ids=["@somechannel", "@otherchannel"])
```

Exclusions narrow any of them:

```python
InputAdTargetChannels(
    language_codes=["en"],
    topic_ids=[12],
    exclude_topic_ids=[40],                    # included + excluded topics ≤ 20
    exclude_channel_ids=["@competitor"],       # included + excluded channels ≤ 100
)
```

## Users

Targets people rather than places. Every field is optional except `country_codes`, which the API always expects (it may be empty).

```python
from telead import InputAdTargetUsers

InputAdTargetUsers(
    country_codes=["DE", "AT", "CH"],       # up to 8
    language_codes=["de"],                  # up to 8 — the user's language
    topic_ids=[12, 31],                     # interests
    intersect_topics=True,                  # all topics, not any
    device="android",                       # ios, android, mobile or desktop
    exclude_political_channels=True,
)
```

| Field | |
|---|---|
| `country_codes` | Up to 8 ISO codes. **Exactly one** when `location_ids` is used. |
| `location_ids` | Up to 20 cities or regions, all in that one country — see [Locations](#locations). |
| `language_codes` | Up to 8 IETF tags, from `get_target_languages_list()`. |
| `topic_ids`, `exclude_topic_ids` | Interests, from `get_target_topics_list()`; 20 in total. |
| `intersect_topics` | Users with **all** listed interests instead of any. |
| `channel_ids`, `exclude_channel_ids` | Audiences of channels — people who read them; 100 in total. |
| `audience_ids`, `exclude_audience_ids` | [Retargeting audiences](audiences.md); up to 4 each. |
| `device` | `ios`, `android`, `mobile` or `desktop`. |
| `exclude_political_channels` | Never show in political channels. |
| `political_channels_only` | Show only in political channels. |

## Bots

```python
from telead import InputAdTargetBots

InputAdTargetBots(bot_ids=["@somebot", "@anotherbot"])     # up to 100
```

## Search

```python
from telead import InputAdTargetSearch

InputAdTargetSearch(search_queries=["crypto wallet", "ton wallet"])   # up to 10
```

A search ad needs no `text`:

```python
client.create_ad(
    title="Wallet — search",
    promote_url="https://t.me/wallet",
    cpm=4,
    placement="search_result",
    target=InputAdTargetSearch(["crypto wallet"]),
)
```

## Resolving channels and bots

Channels and bots are named as `"@username"` or by numeric id — but **a numeric id works only after this account has resolved that channel or bot by username**. Otherwise the API answers `CHANNEL_ID_UNKNOWN` / `BOT_ID_UNKNOWN`, raised as [`UnknownPeerError`](errors.md).

So usernames are the safe default. To check a list before creating an ad, or to get ids to store, resolve each one:

```python
from telead import UnknownPeerError

for username in ["@somechannel", "@otherchannel"]:
    try:
        channel = client.get_target_channel(username)
    except UnknownPeerError:
        print(f"{username} cannot be targeted")
    else:
        print(channel.channel_id, channel.title)
```

`get_target_channel(..., for_excluding=True)` resolves a channel you mean to **exclude**. `get_target_bot("@somebot")` does the same for bots.

!!! note "Big ids"
    Channel and bot ids can be longer than 32 bits (up to 52 significant bits). Python handles them natively; store them in a 64-bit column.

## The catalogue

What you can target — call these once and cache the result:

```python
languages = client.get_target_languages_list()   # [TargetLanguage(language_code='en', name='English'), …]
topics = client.get_target_topics_list()         # [TargetTopic(topic_id=12, name='…'), …]
countries = client.get_target_countries_list()   # [TargetCountry(country_code='DE', name='Germany'), …]
```

### Locations

Locations are searched by name within one country:

```python
for location in client.iter_target_locations("DE", "Berlin"):
    print(location.location_id, location.name, location.region)

client.get_target_locations_by_id([1234, 5678])
```

## Reading a target back

Pass `return_target=True` and `ad.target` holds an `AdTarget*` object with **names**, not just ids:

```python
ad = client.get_ad(42, return_target=True)
for channel in ad.target.channels:
    print(channel.username, channel.title)
```

See [Models → targets](models.md#targets).
