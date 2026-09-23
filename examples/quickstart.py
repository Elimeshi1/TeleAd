"""Print the account's balance and every ad with its numbers.

    TELEGRAM_ADS_TOKEN=... python examples/quickstart.py
"""

import os

from telead import Client

with Client(os.environ["TELEGRAM_ADS_TOKEN"]) as client:
    account = client.get_current_account()
    print(f"{account.title}: {account.remaining_budget} {account.currency} left, "
          f"{account.ads_budget} in ad budgets")

    for ad in client.iter_ads():
        ctr = f"{ad.ctr:.2%}" if ad.ctr is not None else "—"
        print(f"#{ad.ad_id:<6} {ad.status:<16} {ad.views:>8} views  CTR {ctr:>6}  "
              f"{ad.remaining_budget:>8} left  {ad.title}")
