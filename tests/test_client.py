from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
import requests

from telead import (
    AuthenticationError,
    Client,
    InputAdSchedule,
    InputAdTargetChannels,
    InputAdTargetSearch,
    InputAdTargetUsers,
    InvalidRequestError,
    RateLimitError,
    RequestInProgressError,
    ServerError,
    TransportError,
    UnknownPeerError,
    ValidationError,
)

from .conftest import AD, FakeResponse, FakeSession, fail, ok


def ad_kwargs(**overrides):
    kwargs = dict(
        title="Autumn launch",
        text="Hello",
        promote_url="https://t.me/example",
        cpm=2.5,
        placement="channel_post",
        target=InputAdTargetChannels(channel_ids=["@example"]),
    )
    kwargs.update(overrides)
    return kwargs


# ---------------------------------------------------------------------- #
# Transport
# ---------------------------------------------------------------------- #


class TestRequests:
    def test_method_url_auth_and_json_body(self, client, session):
        session.queue(ok({"account_id": "abc", "title": "Main", "currency": "EUR",
                          "spent_budget": 1, "remaining_budget": 9, "ads_budget": 3}))
        account = client.get_current_account()

        request = session.last
        assert request["method"] == "POST"
        assert request["url"] == "https://api.test/getCurrentAccount"
        assert request["headers"]["Authorization"] == "Bearer TOKEN"
        assert request["headers"]["User-Agent"].startswith("telead/")
        assert request["json"] == {}
        assert account.account_id == "abc"
        assert account.currency_info.cpm_precision == 2

    def test_none_parameters_are_dropped(self, client, session):
        client.get_ads_list(limit=10)
        assert session.last_json == {"limit": 10}

    def test_lists_are_sent_as_json_arrays(self, client, session):
        session.queue(ok([AD]))
        ads = client.get_ads_by_id([42, 43])
        assert session.last_json == {"ad_ids": [42, 43]}
        assert ads[0].ad_id == 42

    def test_empty_token_is_rejected(self):
        with pytest.raises(ValidationError):
            Client("")

    def test_context_manager_closes_own_session_only(self, session):
        with Client("T", session=session):
            pass
        assert session.closed is False

        own = Client("T")
        closed = []
        own._session.close = lambda: closed.append(True)  # type: ignore[method-assign]
        with own:
            pass
        assert closed == [True]

    def test_raw_call(self, client, session):
        session.queue(ok({"anything": 1}))
        assert client.call("someFutureMethod", {"a": 1, "b": None}) == {"anything": 1}
        assert session.last_method == "someFutureMethod"
        assert session.last_json == {"a": 1}


# ---------------------------------------------------------------------- #
# Errors and retries
# ---------------------------------------------------------------------- #


class TestErrors:
    def test_error_code_raises_mapped_class(self, client, session):
        session.queue(fail("ACCESS_TOKEN_INVALID"))
        with pytest.raises(AuthenticationError) as info:
            client.get_current_account()
        assert info.value.code == "ACCESS_TOKEN_INVALID"
        assert info.value.method == "getCurrentAccount"
        assert info.value.status == 200
        assert "ACCESS_TOKEN_INVALID" in str(info.value)

    def test_invalid_suffix_maps_to_invalid_request(self, client, session):
        session.queue(fail("AD_TITLE_REQUIRED"))
        with pytest.raises(InvalidRequestError):
            client.call("createAd", {})

    def test_unknown_peer(self, client, session):
        session.queue(fail("CHANNEL_ID_UNKNOWN"))
        with pytest.raises(UnknownPeerError):
            client.get_target_channel(12345)

    def test_client_errors_are_not_retried(self, client, session):
        session.queue(fail("AD_ID_INVALID"))
        with pytest.raises(InvalidRequestError):
            client.get_ad(1)
        assert len(session.requests) == 1

    def test_server_error_on_read_is_retried(self, client, session, no_sleep):
        session.queue(FakeResponse(502, text="Bad Gateway"), ok([]))
        assert client.get_target_topics_list() == []
        assert len(session.requests) == 2
        assert len(no_sleep) == 1

    def test_server_error_on_unkeyed_write_is_not_retried(self, client, session):
        session.queue(FakeResponse(500, text="oops"))
        with pytest.raises(ServerError):
            client.delete_ad(1)
        assert len(session.requests) == 1

    def test_transport_error_on_unkeyed_write_is_not_retried(self, client, session):
        session.queue(requests.ConnectionError("reset"))
        with pytest.raises(TransportError):
            client.submit_ad_for_review(1)
        assert len(session.requests) == 1

    def test_transport_error_on_keyed_write_is_retried_with_same_key(self, client, session):
        session.queue(requests.ConnectionError("reset"), ok(AD))
        ad = client.create_ad(**ad_kwargs())
        assert ad.ad_id == 42
        keys = [r["headers"]["Idempotency-Key"] for r in session.requests]
        assert len(keys) == 2 and keys[0] == keys[1]

    def test_request_in_progress_is_retried(self, client, session):
        session.queue(fail("IDEMPOTENT_REQUEST_IN_PROGRESS"), ok(AD))
        client.increase_ad_budget(42, 10)
        assert len(session.requests) == 2

    def test_request_in_progress_gives_up(self, session):
        client = Client("T", session=session, max_retries=1)
        session.queue(*[fail("IDEMPOTENT_REQUEST_IN_PROGRESS")] * 3)
        with pytest.raises(RequestInProgressError):
            client.increase_ad_budget(42, 10)
        assert len(session.requests) == 2

    def test_rate_limit_is_retried_even_on_unkeyed_write(self, client, session, no_sleep):
        session.queue(fail("FLOOD_WAIT_3"), ok(True))
        assert client.delete_ad(1) is True
        assert no_sleep == [3.0]

    def test_http_429_with_retry_after(self, client, session, no_sleep):
        session.queue(FakeResponse(429, text="", headers={"Retry-After": "7"}), ok([]))
        client.get_target_countries_list()
        assert no_sleep == [7.0]

    def test_rate_limit_without_wait_backs_off_from_five_seconds(self, client, session, no_sleep):
        session.queue(fail("TOO_MANY_REQUESTS"), ok([]))
        client.get_target_countries_list()
        assert 5.0 <= no_sleep[0] <= 5.5

    def test_max_retries_zero(self, session):
        client = Client("T", session=session, max_retries=0)
        session.queue(fail("FLOOD_WAIT_1"))
        with pytest.raises(RateLimitError) as info:
            client.get_pixel()
        assert info.value.retry_after == 1.0

    def test_non_envelope_response_is_server_error(self, client, session):
        session.queue(*[FakeResponse(200, text="<html>")] * 4)
        with pytest.raises(ServerError):
            client.get_pixel()


# ---------------------------------------------------------------------- #
# Idempotency
# ---------------------------------------------------------------------- #


class TestIdempotency:
    def test_keyed_methods_get_a_fresh_key_per_call(self, client, session):
        session.queue(ok(AD), ok(AD))
        client.create_ad(**ad_kwargs())
        client.create_ad(**ad_kwargs())
        first, second = (r["headers"]["Idempotency-Key"] for r in session.requests)
        assert first != second and len(first) <= 128

    def test_explicit_key_is_used(self, client, session):
        session.queue(ok({"transaction_id": "t", "status": "completed"}))
        client.increase_account_budget("acc", 5, idempotency_key="order-17")
        assert session.last["headers"]["Idempotency-Key"] == "order-17"
        assert "idempotency_key" not in session.last_json

    def test_unkeyed_methods_get_no_key(self, client, session):
        client.delete_ad(1)
        assert "Idempotency-Key" not in session.last["headers"]

    def test_auto_idempotency_off(self, session):
        client = Client("T", session=session, auto_idempotency=False)
        session.queue(ok(AD))
        client.create_ad(**ad_kwargs())
        assert "Idempotency-Key" not in session.last["headers"]

    def test_key_too_long(self, client):
        with pytest.raises(ValidationError):
            client.create_pixel(idempotency_key="x" * 129)


# ---------------------------------------------------------------------- #
# Account scoping
# ---------------------------------------------------------------------- #


class TestAccountScope:
    def test_client_account_id_fills_scoped_methods(self, session):
        client = Client("T", session=session, account_id="rel")
        client.get_ads_list()
        assert session.last_json == {"account_id": "rel"}

    def test_explicit_account_id_wins(self, session):
        client = Client("T", session=session, account_id="rel")
        client.get_ads_list(account_id="other")
        assert session.last_json == {"account_id": "other"}

    def test_unscoped_methods_are_left_alone(self, session):
        client = Client("T", session=session, account_id="rel")
        session.queue(ok({"transaction_id": "t", "status": "in_progress"}))
        client.increase_account_budget("target", 5)
        assert session.last_json == {"account_id": "target", "amount": 5}
        client.get_target_languages_list()
        assert session.last_json == {}

    def test_with_account_shares_session(self, client, session):
        view = client.with_account("rel")
        view.get_pixel()
        assert session.last_json == {"account_id": "rel"}
        view.close()
        assert session.closed is False
        assert "rel" in repr(view)


# ---------------------------------------------------------------------- #
# Ads
# ---------------------------------------------------------------------- #


class TestAds:
    def test_create_ad_payload(self, client, session):
        session.queue(ok(AD))
        schedule = InputAdSchedule.every_day(range(9, 18), timezone=3600)
        ad = client.create_ad(**ad_kwargs(
            initial_budget=50, schedule=schedule, show_userpic=True,
            activate_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
        ))
        body = session.last_json
        assert session.last_method == "createAd"
        assert body["target"] == {"type": "channels", "channel_ids": ["@example"]}
        assert body["schedule"] == {"week_hours_mask": [0b111111111000000000] * 7, "timezone": 3600}
        assert body["activate_date"] == 1790812800
        assert body["initial_budget"] == 50
        assert body["show_userpic"] is True
        assert "photo_id" not in body
        assert ad.ad_id == 42 and ad.ctr == 0.025

    def test_create_ad_accepts_dict_target(self, client, session):
        session.queue(ok(AD))
        client.create_ad(**ad_kwargs(target={"type": "bots", "bot_ids": ["@bot"]},
                                     placement="bot_banner"))
        assert session.last_json["target"] == {"type": "bots", "bot_ids": ["@bot"]}

    def test_search_ad_needs_no_text(self, client, session):
        session.queue(ok(AD))
        client.create_ad(**ad_kwargs(text=None, placement="search_result",
                                     target=InputAdTargetSearch(["crypto wallet"])))
        assert "text" not in session.last_json

    @pytest.mark.parametrize("overrides, message", [
        ({"text": None}, "text is required"),
        ({"text": "x" * 161}, "text"),
        ({"title": "ש" * 65}, "bytes"),
        ({"placement": "banner"}, "placement"),
        ({"button": "click_me"}, "button"),
        ({"photo_id": "p", "video_id": "v"}, "not both"),
        ({"impression_frequency": 5}, "impression_frequency"),
        ({"cpm": 0}, "cpm"),
        ({"target": {"type": "nope"}}, "target type"),
        ({"target": InputAdTargetChannels(channel_ids=["@a"], topic_ids=[1])}, "channel_ids"),
        ({"schedule": InputAdSchedule([1] * 7)}, "timezone"),
    ])
    def test_create_ad_validation(self, client, session, overrides, message):
        with pytest.raises(ValidationError, match=message):
            client.create_ad(**ad_kwargs(**overrides))
        assert session.requests == []

    def test_validation_off_sends_anyway(self, session):
        client = Client("T", session=session, validate=False)
        session.queue(ok(AD))
        client.create_ad(**ad_kwargs(text="x" * 500))
        assert len(session.requests) == 1

    def test_edit_ad_remove_schedule(self, client, session):
        session.queue(ok(AD))
        client.edit_ad(42, schedule=False, daily_budget_limit=0)
        assert session.last_json == {"ad_id": 42, "schedule": False, "daily_budget_limit": 0}

    def test_pause_and_resume(self, client, session):
        session.queue(ok(AD), ok(AD))
        client.pause_ad(42)
        assert session.last_json == {"ad_id": 42, "is_paused": True}
        client.resume_ad(42)
        assert session.last_json == {"ad_id": 42, "is_paused": False}

    def test_get_ad_returns_none_when_missing(self, client, session):
        session.queue(ok([]))
        assert client.get_ad(1) is None

    def test_iter_ads_follows_next_offset(self, client, session):
        session.queue(
            ok({"total_count": 3, "ads": [AD, AD], "next_offset": "abc"}),
            ok({"total_count": 3, "ads": [AD]}),
        )
        assert len(list(client.iter_ads(page_size=2))) == 3
        assert session.requests[0]["json"] == {"limit": 2}
        assert session.requests[1]["json"] == {"limit": 2, "offset": "abc"}

    def test_ads_list_limit_cap(self, client):
        with pytest.raises(ValidationError):
            client.get_ads_list(limit=101)

    def test_delete_ad_returns_bool(self, client, session):
        session.queue(ok(True))
        assert client.delete_ad(42) is True


# ---------------------------------------------------------------------- #
# Stats
# ---------------------------------------------------------------------- #


class TestStats:
    def test_ad_stats_with_datetimes(self, client, session):
        session.queue(ok([{"from_time": 0, "to_time": 86400, "views": 5, "joins": 2}]))
        items = client.get_ad_stats(
            42, datetime(2026, 9, 1, tzinfo=timezone.utc), datetime(2026, 9, 8, tzinfo=timezone.utc)
        )
        assert session.last_json == {"ad_id": 42, "from_time": 1788220800,
                                     "to_time": 1788825600, "interval": 86400}
        assert items[0].actions == 2  # the old "joins" name still parses

    def test_period_cap(self, client):
        with pytest.raises(ValidationError, match="1000"):
            client.get_account_stats(0, 300 * 1001, 300)

    def test_bad_interval(self, client):
        with pytest.raises(ValidationError, match="interval"):
            client.get_account_stats(0, 3600, 3600)

    def test_report_ranges(self, client, session):
        with pytest.raises(ValidationError):
            client.get_account_report(2026, 13)
        session.queue(ok([{"ad_id": 1, "views": 9}]))
        items = client.get_account_report(2026, 9)
        assert items[0].views == 9


# ---------------------------------------------------------------------- #
# Budgets
# ---------------------------------------------------------------------- #


class TestBudgets:
    def test_wait_for_transaction(self, client, session, no_sleep):
        session.queue(
            ok({"transaction_id": "t1", "status": "in_progress"}),
            ok({"transaction_id": "t1", "status": "in_progress"}),
            ok({"transaction_id": "t1", "status": "completed", "amount": 5}),
        )
        pending = client.increase_account_budget("acc", 5)
        final = client.wait_for_transaction(pending, interval=0.01)
        assert final.is_completed and final.amount == 5
        assert [r["url"].rsplit("/", 1)[1] for r in session.requests] == [
            "increaseAccountBudget", "getTransactionStatus", "getTransactionStatus",
        ]

    def test_wait_for_transaction_timeout(self, client, session):
        session.queue(*[ok({"transaction_id": "t", "status": "in_progress"})] * 5)
        with pytest.raises(TimeoutError):
            client.wait_for_transaction("t", timeout=0, interval=1)

    def test_amount_must_be_positive(self, client):
        with pytest.raises(ValidationError):
            client.decrease_ad_budget(1, -5)

    def test_iter_account_transactions(self, client, session):
        session.queue(
            ok({"total_count": 2, "transactions": [
                {"peer": {"type": "external", "comment": "INV-1"}, "date": 1, "amount": 100}],
                "next_offset": "1"}),
            ok({"total_count": 2, "transactions": [
                {"peer": {"type": "ad", "ad_id": 4, "ad_title": "x"}, "date": 2, "amount": -3}]}),
        )
        items = list(client.iter_account_transactions())
        assert items[0].peer.comment == "INV-1"
        assert items[1].peer.ad_id == 4

    def test_iter_related_accounts_by_count(self, client, session):
        session.queue(
            ok({"total_count": 3, "accounts": [{"account_id": "a"}, {"account_id": "b"}]}),
            ok({"total_count": 3, "accounts": [{"account_id": "c"}]}),
        )
        ids = [a.account_id for a in client.iter_related_accounts(page_size=2)]
        assert ids == ["a", "b", "c"]
        assert session.requests[1]["json"] == {"offset": 2, "limit": 2}


# ---------------------------------------------------------------------- #
# Uploads
# ---------------------------------------------------------------------- #

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 100


class TestUploads:
    def test_upload_photo_multipart(self, session, tmp_path):
        client = Client("T", session=session, account_id="rel")
        path = tmp_path / "banner.jpg"
        path.write_bytes(JPEG)
        session.queue(ok({"photo_id": "p1", "photo_url": "https://x/p1.jpg"}))
        photo = client.upload_ad_photo(path)

        request = session.last
        assert request["url"].endswith("/uploadAdPhoto")
        assert request["files"]["file"] == ("banner.jpg", JPEG, "image/jpeg")
        assert request["data"] == {"account_id": "rel"}
        assert "json" not in request
        assert photo.photo_id == "p1"

    def test_upload_video_from_bytes(self, client, session):
        session.queue(ok({"video_id": "v1", "video_url": "u"}))
        assert client.upload_ad_video(MP4).video_id == "v1"
        assert session.last["files"]["file"][2] == "video/mp4"

    def test_upload_rejects_wrong_format(self, client):
        with pytest.raises(ValidationError, match="image/jpeg"):
            client.upload_ad_photo(MP4, filename="clip.mp4")

    def test_upload_rejects_oversize(self, client):
        with pytest.raises(ValidationError, match="bytes"):
            client.upload_website_photo(JPEG + b"\x00" * (1024 * 1024))

    def test_upload_rejects_text_mode_file(self, client, tmp_path):
        path = tmp_path / "a.jpg"
        path.write_bytes(JPEG)
        with open(path, "r", encoding="latin-1") as handle:
            with pytest.raises(ValidationError, match="binary"):
                client.upload_ad_photo(handle)


# ---------------------------------------------------------------------- #
# Audiences, pixel, targeting
# ---------------------------------------------------------------------- #


class TestAudiences:
    def test_create_small_audience(self, client, session):
        session.queue(ok({"audience_id": 7, "title": "VIP", "size": 50}))
        audience = client.create_audience("VIP", ["+15550000001"])
        assert session.last_json == {"title": "VIP", "add_phones": ["+15550000001"]}
        assert "Idempotency-Key" in session.last["headers"]
        assert audience.audience_id == 7

    def test_create_large_audience_batches_the_rest(self, client, session):
        phones = [f"+1555{i:07d}" for i in range(25_000)]
        session.queue(ok({"audience_id": 7}), ok({"audience_id": 7}), ok({"audience_id": 7, "size": 25_000}))
        audience = client.create_audience("Big", phones)
        sizes = [len(r["json"].get("add_phones", [])) for r in session.requests]
        assert sizes == [10_000, 10_000, 5_000]
        assert [r["url"].rsplit("/", 1)[1] for r in session.requests] == [
            "createAudience", "editAudience", "editAudience",
        ]
        assert audience.size == 25_000

    def test_edit_audience_cap(self, client):
        with pytest.raises(ValidationError, match="10000"):
            client.edit_audience(7, add_phones=["1"] * 10_001)

    def test_remove_phones_batches(self, client, session):
        session.queue(ok({"audience_id": 7}), ok({"audience_id": 7}))
        client.remove_audience_phones(7, ["a", "b", "c"], batch_size=2)
        assert [r["json"]["remove_phones"] for r in session.requests] == [["a", "b"], ["c"]]


class TestPixelAndTargeting:
    def test_create_pixel_event(self, client, session):
        session.queue(ok({"event_id": "e1", "title": "Buy", "type": "purchase", "status": "inactive"}))
        event = client.create_pixel_event("Buy", "purchase")
        assert session.last_json == {"title": "Buy", "type": "purchase"}
        assert event.event_id == "e1"

    def test_pixel_event_type_validation(self, client):
        with pytest.raises(ValidationError, match="type"):
            client.create_pixel_event("Buy", "landing_view")

    def test_get_target_channel_by_username(self, client, session):
        session.queue(ok({"channel_id": 1234567890123, "title": "Durov", "username": "durov"}))
        channel = client.get_target_channel("@durov", for_excluding=True)
        assert session.last_json == {"channel_id": "@durov", "for_excluding": True}
        assert channel.channel_id == 1234567890123

    def test_locations_country_code(self, client):
        with pytest.raises(ValidationError):
            client.get_target_locations_list("ISR", "Tel")

    def test_iter_target_locations(self, client, session):
        session.queue(
            ok({"total_count": 2, "locations": [{"location_id": 1, "name": "A"}], "next_offset": "x"}),
            ok({"total_count": 2, "locations": [{"location_id": 2, "name": "B"}], "next_offset": ""}),
        )
        names = [loc.name for loc in client.iter_target_locations("IL", "Tel")]
        assert names == ["A", "B"]

    def test_users_target_validation(self, client):
        target = InputAdTargetUsers(country_codes=["IL", "US"], location_ids=[1])
        with pytest.raises(ValidationError, match="exactly one"):
            client.create_ad(**ad_kwargs(target=target))


def test_multipart_form_values_are_json_serialized(session):
    from telead.client import _form_value

    assert _form_value([1, 2]) == "[1,2]"
    assert _form_value(True) == "true"
    assert json.loads(_form_value({"a": 1})) == {"a": 1}
    assert _form_value(5) == "5"


def test_fake_session_type_is_accepted():
    # Client takes any object with request() and close(); tests rely on it.
    Client("T", session=FakeSession())  # type: ignore[arg-type]
