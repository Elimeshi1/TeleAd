from __future__ import annotations

from datetime import datetime, timezone

import pytest

from telead import InputAdSchedule, InputAdTargetChannels, InputAdTargetUsers, ValidationError
from telead.limits import CURRENCIES
from telead.models import (
    Ad,
    AdTargetBots,
    AdTargetSearch,
    AdTargetUsers,
    AdTransaction,
    AdTransactionPeerViews,
    PixelEvent,
    TransactionStatus,
    UnknownObject,
)

from .conftest import AD


class TestAd:
    def test_basic_fields(self):
        ad = Ad.from_dict(AD)
        assert ad.ad_id == 42
        assert ad.currency_info is CURRENCIES["TON"]
        assert ad.created_at == datetime.fromtimestamp(1726000000, tz=timezone.utc)
        assert ad.is_active and not ad.is_declined
        assert ad.opens is None and ad.photo is None
        assert ad.raw is AD

    def test_nested_objects(self):
        ad = Ad.from_dict({
            **AD,
            "status": "declined",
            "decline_reason": {"text": "Misleading", "description_html": "<b>no</b>"},
            "photo": {"photo_id": "p", "photo_url": "u"},
            "website_photo": {"photo_id": "w", "photo_url": "u2"},
            "schedule": {"week_hours_mask": [0, 0, 0, 0, 0, 0, 0]},
            "target": {"type": "users", "countries": [{"country_code": "IL", "name": "Israel"}],
                       "audiences": [{"audience_id": 3, "title": "VIP"}], "device": "ios"},
        })
        assert ad.decline_reason.text == "Misleading"
        assert ad.photo.photo_id == "p" and ad.website_photo.photo_id == "w"
        assert not ad.schedule.is_set
        assert isinstance(ad.target, AdTargetUsers)
        assert ad.target.countries[0].name == "Israel"
        assert ad.target.audiences[0].audience_id == 3

    @pytest.mark.parametrize("data, cls", [
        ({"type": "bots", "bots": [{"bot_id": 1, "username": "b"}]}, AdTargetBots),
        ({"type": "search", "search_queries": ["a"]}, AdTargetSearch),
        ({"type": "brand_new"}, UnknownObject),
    ])
    def test_target_variants(self, data, cls):
        assert isinstance(Ad.from_dict({"target": data}).target, cls)

    def test_joins_alias(self):
        assert Ad.from_dict({"joins": 7}).actions == 7
        assert Ad.from_dict({"joins": 7, "actions": 9}).actions == 9

    def test_ready_for_review(self):
        assert Ad.from_dict({"status": "ready_for_review"}).needs_review_submission

    def test_ctr_without_views(self):
        assert Ad.from_dict({"clicks": 5, "views": 0}).ctr is None

    def test_garbage_input(self):
        assert Ad.from_dict(None).ad_id == 0  # type: ignore[arg-type]


def test_transaction_status_flags():
    status = TransactionStatus.from_dict({
        "status": "failed", "error": "NOT_ENOUGH_BUDGET",
        "main_account": {"account_id": "m"}, "related_account": {"account_id": "r"},
    })
    assert status.is_failed and not status.is_pending
    assert status.main_account.account_id == "m"
    assert status.error == "NOT_ENOUGH_BUDGET"


def test_ad_transaction_peer():
    transaction = AdTransaction.from_dict({"peer": {"type": "views", "views": 1000},
                                           "date": 0, "amount": -2.5})
    assert isinstance(transaction.peer, AdTransactionPeerViews)
    assert transaction.when == datetime(1970, 1, 1, tzinfo=timezone.utc)


def test_pixel_event_dates():
    event = PixelEvent.from_dict({"event_id": "e", "created_date": 60, "auto_created": True})
    assert event.last_triggered_at is None
    assert event.created_at.minute == 1
    assert event.auto_created


class TestCurrencies:
    def test_precision(self):
        assert CURRENCIES["XTR"].round_cpm(10.6) == 11
        assert CURRENCIES["EUR"].round_cpm(1.005) in (1.0, 1.01)
        assert CURRENCIES["TON"].round_amount(1.1234567) == 1.12346


class TestSchedule:
    def test_every_day(self):
        schedule = InputAdSchedule.every_day([0, 23], timezone=0)
        assert schedule.week_hours_mask == [(1 << 23) | 1] * 7
        assert schedule.hours(3) == [0, 23]

    def test_weekly_by_name_and_index(self):
        schedule = InputAdSchedule.weekly({"Monday": [9], 6: [10]}, use_viewer_timezone=True)
        schedule.validate()
        assert schedule.to_dict() == {"week_hours_mask": [512, 0, 0, 0, 0, 0, 1024],
                                      "use_viewer_timezone": True}

    @pytest.mark.parametrize("build", [
        lambda: InputAdSchedule.every_day([24], timezone=0),
        lambda: InputAdSchedule.weekly({"funday": [1]}, timezone=0),
        lambda: InputAdSchedule.weekly({7: [1]}, timezone=0),
    ])
    def test_bad_hours_and_days(self, build):
        with pytest.raises(ValidationError):
            build()

    def test_bad_timezone(self):
        with pytest.raises(ValidationError, match="UTC offset"):
            InputAdSchedule.every_day([1], timezone=1234).validate()

    def test_wrong_length(self):
        with pytest.raises(ValidationError, match="7"):
            InputAdSchedule([0] * 6, timezone=0).validate()

    def test_empty_schedule_needs_no_timezone(self):
        InputAdSchedule().validate()


class TestTargets:
    def test_channels_topics_need_one_language(self):
        with pytest.raises(ValidationError, match="exactly one"):
            InputAdTargetChannels(topic_ids=[1], language_codes=["en", "ru"]).validate()
        InputAdTargetChannels(topic_ids=[1], language_codes=["en"]).validate()

    def test_combined_caps(self):
        with pytest.raises(ValidationError, match="20"):
            InputAdTargetChannels(language_codes=["en"], topic_ids=list(range(15)),
                                  exclude_topic_ids=list(range(6))).validate()
        with pytest.raises(ValidationError, match="100"):
            InputAdTargetUsers(country_codes=["IL"], channel_ids=["@a"] * 60,
                               exclude_channel_ids=["@b"] * 41).validate()

    def test_audience_cap_per_side(self):
        with pytest.raises(ValidationError, match="audience_ids"):
            InputAdTargetUsers(country_codes=["IL"], audience_ids=[1] * 5).validate()

    def test_peer_format(self):
        with pytest.raises(ValidationError, match="@username"):
            InputAdTargetChannels(channel_ids=["durov"]).validate()
        InputAdTargetChannels(channel_ids=["@durov", 123, "-100123"]).validate()

    def test_device(self):
        with pytest.raises(ValidationError, match="device"):
            InputAdTargetUsers(country_codes=["IL"], device="tv").validate()

    def test_users_to_dict_keeps_country_codes(self):
        assert InputAdTargetUsers().to_dict() == {"type": "users", "country_codes": []}
