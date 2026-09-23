# Recipes

## Keep the token out of the code

```python
import os
from telead import Client

client = Client(os.environ["TELEGRAM_ADS_TOKEN"])
```

## An agency: one client per related account

```python
for account in client.iter_related_accounts():
    view = client.with_account(account.account_id)
    active = [ad for ad in view.iter_ads() if ad.is_active]
    print(f"{account.title}: {len(active)} active, {account.remaining_budget} {account.currency} left")
```

## Many accounts in parallel

`Client` is thread-safe, so a thread pool works for read-heavy jobs such as reports:

```python
from concurrent.futures import ThreadPoolExecutor

def summary(account):
    view = client.with_account(account.account_id)
    return account.title, sum(ad.spent_budget for ad in view.iter_ads())

with ThreadPoolExecutor(max_workers=4) as pool:
    for title, spent in pool.map(summary, client.iter_related_accounts()):
        print(title, spent)
```

Keep the pool small. The API does not publish rate limits, and the client backs off if it meets one — but a handful of workers is plenty.

## Top up accounts that run low

```python
from telead import NotEnoughBudgetError

THRESHOLD, TARGET = 50, 200

for account in client.iter_related_accounts():
    if account.remaining_budget >= THRESHOLD:
        continue
    try:
        pending = client.increase_account_budget(account.account_id, TARGET - account.remaining_budget)
    except NotEnoughBudgetError:
        break
    final = client.wait_for_transaction(pending)
    print(account.title, final.status, final.error or "")
```

The full script is [`examples/top_up_accounts.py`](https://github.com/Elimeshi1/TeleAd/blob/main/examples/top_up_accounts.py).

## Make a scheduled job safe to rerun

A job that pays out on a schedule may be retried by its scheduler after a crash. Derive the idempotency key from what the payment *is*, so a rerun within 24 hours replays instead of paying twice:

```python
from datetime import date

key = f"weekly-topup-{account.account_id}-{date.today().isocalendar()[1]}"
client.increase_account_budget(account.account_id, 100, idempotency_key=key)
```

## Pause everything that is over its daily budget

```python
for ad in client.iter_ads():
    if ad.daily_budget_limit and ad.daily_spent_budget is not None \
            and ad.daily_spent_budget >= ad.daily_budget_limit and not ad.is_paused:
        client.pause_ad(ad.ad_id)
```

## Raise the CPM of every active ad by 10 %

```python
account = client.get_current_account()
rules = account.currency_info

for ad in client.iter_ads():
    if ad.is_active:
        client.edit_ad(ad.ad_id, cpm=rules.round_cpm(ad.cpm * 1.1))
```

Remember that an edit sends an ad with a budget back to review.

## Copy an ad to another account

Photo and video ids belong to one account, so upload the media again in the destination:

```python
import requests

source = client.get_ad(ad_id, return_target=True)
dest = client.with_account("rel-456")

photo_id = None
if source.photo:
    image = requests.get(source.photo.photo_url, timeout=30).content
    photo_id = dest.upload_ad_photo(image, filename="photo.jpg").photo_id

dest.create_ad(
    title=source.title,
    text=source.text,
    promote_url=source.promote_url,
    cpm=source.cpm,
    placement=source.placement,
    photo_id=photo_id,
    # a channels target here; rebuild other types the same way
    target={"type": "channels",
            "channel_ids": [f"@{c.username}" if c.username else c.channel_id
                            for c in source.target.channels]},
)
```

The returned target has full objects (`source.target.channels`), not the ids you sent, so it has to be rebuilt as an input — here from the channels' usernames.

## Clean up old ads

```python
from datetime import datetime, timedelta, timezone

cutoff = datetime.now(timezone.utc) - timedelta(days=90)
for ad in client.iter_ads():
    if ad.status == "stopped" and ad.created_at < cutoff:
        if ad.remaining_budget:
            client.decrease_ad_budget(ad.ad_id, ad.remaining_budget)
        client.delete_ad(ad.ad_id)
```

Both `decrease_ad_budget` and `delete_ad` need the ad to have been inactive for 10 minutes.

## Log what the client does

```python
import logging

logging.basicConfig(level=logging.INFO)
logging.getLogger("telead").setLevel(logging.DEBUG)
logging.getLogger("urllib3").setLevel(logging.DEBUG)   # every HTTP request
```

Never log the token: it is in the `Authorization` header, which `urllib3` does not print.
