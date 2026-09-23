# Retargeting audiences

`createAudience`, `editAudience`, `deleteAudience`, `getAudiencesById`, `getAudiencesList`.

An audience is a list of phone numbers — your customers, say — that a **users** target can include or exclude.

## Create

```python
audience = client.create_audience("Customers 2026", phones)
print(audience.audience_id, audience.size)
```

`phones` is a list of phone numbers, or of their SHA-256 hashes. The API accepts up to 10,000 per call and up to 1,000,000 in an audience; `create_audience` takes any number up to that. It creates the audience with the first 10,000 and adds the rest in batches.

`title` is 1–64 characters and only shown in the Telegram Ads interface.

!!! note "Hashing"
    The API accepts phone numbers or their SHA-256 hashes, and the library sends what you give it unchanged. The docs do not specify how a number should be normalized before hashing, so if you hash, build a small test audience first and check its `size`.

## Size

`size` is approximate. `0` means empty, and `50` means fewer than 100 numbers — small audiences are not counted exactly.

## Use in an ad

```python
from telead import InputAdTargetUsers

target = InputAdTargetUsers(
    country_codes=["DE"],
    audience_ids=[audience.audience_id],       # up to 4
    exclude_audience_ids=[existing_buyers],    # up to 4
)
```

## Change

```python
client.edit_audience(audience_id, title="Customers — 2026")

client.add_audience_phones(audience_id, new_customers)        # any number, in batches
client.remove_audience_phones(audience_id, unsubscribed)      # any number, in batches

client.edit_audience(audience_id, reset_phones=True, add_phones=fresh_list)   # replace
```

`edit_audience` does it all in one call, up to 10,000 numbers per list: removals, or the reset, happen **before** additions, and `remove_phones` is ignored when `reset_phones` is set. `add_audience_phones` and `remove_audience_phones` split any list into calls of 10,000.

## List and delete

```python
for audience in client.get_audiences_list():
    print(audience.audience_id, audience.title, audience.size, audience.ads_count)

client.get_audiences_by_id([7, 8])

client.delete_audience(audience_id)     # only if no ad uses it — check ads_count
```
