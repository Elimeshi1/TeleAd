"""Create a photo ad in a handful of channels, paused until tomorrow 09:00 UTC.

    TELEGRAM_ADS_TOKEN=... python examples/create_channel_ad.py banner.jpg
"""

import os
import sys
from datetime import datetime, time, timedelta, timezone

from telead import Client, InputAdSchedule, InputAdTargetChannels, UnknownPeerError

CHANNELS = ["@telegram", "@durov"]

with Client(os.environ["TELEGRAM_ADS_TOKEN"]) as client:
    # Resolve every channel by username first: it fails fast on a typo, and
    # afterwards the numeric ids are usable too.
    for username in CHANNELS:
        try:
            channel = client.get_target_channel(username)
        except UnknownPeerError:
            sys.exit(f"{username} cannot be targeted")
        print(f"{username}: {channel.title} ({channel.channel_id})")

    photo = client.upload_ad_photo(sys.argv[1])

    tomorrow_9am = datetime.combine(
        datetime.now(timezone.utc).date() + timedelta(days=1), time(9), tzinfo=timezone.utc
    )
    ad = client.create_ad(
        title="Autumn launch — channels",
        text="Everything you need to know about the launch, in one channel.",
        photo_id=photo.photo_id,
        promote_url="https://t.me/telegram",
        cpm=3.0,
        placement="channel_post",
        target=InputAdTargetChannels(channel_ids=CHANNELS),
        initial_budget=20,
        activate_date=tomorrow_9am,
        # Working hours only, Monday to Friday.
        schedule=InputAdSchedule.weekly(
            {day: range(9, 18) for day in ("mon", "tue", "wed", "thu", "fri")}, timezone=0,
        ),
        return_target=True,
    )
    print(f"Created ad #{ad.ad_id}: {ad.status}, starts {ad.activate_at}")
    if ad.needs_review_submission:
        ad = client.submit_ad_for_review(ad.ad_id)
        print(f"Submitted for review: {ad.status}")
