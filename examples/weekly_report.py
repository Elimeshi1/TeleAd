"""Write last week's daily stats for every ad to a CSV file.

    TELEGRAM_ADS_TOKEN=... python examples/weekly_report.py report.csv
"""

import csv
import os
import sys
from datetime import datetime, timedelta, timezone

from telead import Client

today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
start = today - timedelta(days=7)

with Client(os.environ["TELEGRAM_ADS_TOKEN"]) as client, \
        open(sys.argv[1], "w", newline="") as handle:
    writer = csv.writer(handle)
    writer.writerow(["ad_id", "title", "day", "views", "clicks", "actions", "spent", "currency"])
    for ad in client.iter_ads():
        for item in client.get_ad_stats(ad.ad_id, start, today, interval=86400):
            writer.writerow([ad.ad_id, ad.title, item.start.date(), item.views, item.clicks,
                             item.actions, item.spent_budget, item.currency])
print(f"Wrote {sys.argv[1]}")
