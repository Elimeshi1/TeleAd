"""A synchronous client for the Telegram Ads API."""

from __future__ import annotations

import json
import logging
import mimetypes
import os
import random
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Mapping, Sequence

import requests

from . import limits as _limits
from .errors import (
    APIError,
    RateLimitError,
    TransportError,
    ValidationError,
    error_from_response,
)
from .inputs import InputAdSchedule, serialize, validate_input
from .models import (
    Account,
    AccountInfo,
    AccountReportItem,
    AccountTransaction,
    AccountTransactionsList,
    Ad,
    AdList,
    AdPhoto,
    AdStatItem,
    AdTransaction,
    AdTransactionsList,
    AdVideo,
    Audience,
    AudiencesList,
    Pixel,
    PixelEvent,
    PixelEventsList,
    RelatedAccountsList,
    TargetBot,
    TargetChannel,
    TargetCountry,
    TargetLanguage,
    TargetLocation,
    TargetLocationList,
    TargetTopic,
    TransactionStatus,
    WebsitePhoto,
)

__all__ = ["Client"]

log = logging.getLogger("telead")


#: Smallest first backoff after a rate limit that carried no wait time.
_RATE_LIMIT_BACKOFF_BASE = 5.0

#: Methods whose optional ``account_id`` means "act on this account instead of
#: the current one" — the ones a client-wide ``account_id`` fills in.
_SCOPED_METHODS = frozenset({
    "editAccountInfo", "getAccountInfo", "getAccountTransactionsList",
    "getAccountStats", "getAccountReport",
    "uploadAdPhoto", "uploadAdVideo", "uploadWebsitePhoto",
    "createAd", "editAd", "increaseAdBudget", "decreaseAdBudget",
    "submitAdForReview", "deleteAd", "getAdsById", "getAdsList",
    "getAdTransactionsList", "getAdStats",
    "createAudience", "editAudience", "deleteAudience",
    "getAudiencesById", "getAudiencesList",
    "createPixel", "getPixel", "createPixelEvent", "editPixelEvent",
    "deletePixelEvent", "getPixelEventsById", "getPixelEventsList",
})

#: Writes that set absolute state, so sending one twice ends where sending it
#: once does.  With the reads and the idempotency-keyed methods, these are the
#: calls retried after a failure whose outcome is unknown.
_REPEATABLE_WRITES = frozenset({
    "editAccountInfo", "editAd", "editAudience", "editPixelEvent",
})



class Client:
    """Talks to ``https://promoteapi.telegram.org``.

    ::

        from telead import Client

        with Client("<ACCESS_TOKEN>") as client:
            account = client.get_current_account()
            print(account.title, account.remaining_budget, account.currency)

    Args:
        token: The access token from https://ads.telegram.org/account/api.  Sent as
            ``Authorization: Bearer <token>``.  Treat it as a secret.
        account_id: Act on this related account by default.  Every method
            whose ``account_id`` is optional uses it when you leave the
            argument out.  See :meth:`with_account`.
        base_url: Override the API root (useful for tests and proxies).
        timeout: Read timeout in seconds; uploads get at least 120.
        max_retries: Retries after a retryable failure — see *Errors →
            Retries* in the docs.
        backoff_base, backoff_max: Exponential backoff bounds, in seconds.
        auto_idempotency: Give every call to a method that supports
            idempotency keys a fresh UUID, reused across that call's retries,
            so a retried ``createAd`` or budget transfer never runs twice.
        validate: Check lengths, enumerations and targeting caps locally
            before a request leaves.
        session: A pre-built :class:`requests.Session`.
        user_agent: Override the ``User-Agent`` header.
    """

    def __init__(
        self,
        token: str,
        *,
        account_id: str | None = None,
        base_url: str = _limits.DEFAULT_BASE_URL,
        timeout: float = 30.0,
        max_retries: int = 3,
        backoff_base: float = 0.5,
        backoff_max: float = 30.0,
        auto_idempotency: bool = True,
        validate: bool = True,
        session: requests.Session | None = None,
        user_agent: str | None = None,
    ) -> None:
        if not token or not isinstance(token, str):
            raise ValidationError("An access token is required.")

        from . import __version__

        self.token = token
        self.account_id = account_id
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max(0, int(max_retries))
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        self.auto_idempotency = auto_idempotency
        self.validate = validate
        self._session = session or requests.Session()
        self._owns_session = session is None
        self._user_agent = user_agent or f"telead/{__version__}"

    # ------------------------------------------------------------------ #
    # The raw call
    # ------------------------------------------------------------------ #

    def call(
        self,
        method: str,
        params: Mapping[str, Any] | None = None,
        *,
        files: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        """Call any API method by name and return its raw ``result``.

        The typed methods below cover every documented method; use this one
        for a method the platform adds later.  ``None`` values are dropped,
        input objects are serialized, and the client-wide ``account_id``,
        idempotency keys and retries apply as they do everywhere else.

        ::

            client.call("getAdsList", {"limit": 10})
        """
        return self._call(method, dict(params or {}), files=files,
                          idempotency_key=idempotency_key)

    # ------------------------------------------------------------------ #
    # Accounts
    # ------------------------------------------------------------------ #

    def get_current_account(self) -> Account:
        """The account this token belongs to, with its balances."""
        return Account.from_dict(self._call("getCurrentAccount", {}))

    def get_accounts_by_id(self, account_ids: Iterable[str]) -> list[Account]:
        """Accounts by identifier — the current one and its related accounts."""
        ids = _as_list(account_ids)
        if self.validate and not ids:
            raise ValidationError("account_ids must not be empty.")
        return _list_of(Account, self._call("getAccountsById", {"account_ids": ids}))

    def create_account(
        self,
        title: str,
        *,
        full_name: str,
        email: str,
        phone_number: str,
        country: str,
        city: str,
        legal_name: str | None = None,
        idempotency_key: str | None = None,
    ) -> AccountInfo:
        """Create a related account under this (main) account.

        Only the main advertiser account can do this, and only it can manage
        the new account.  Top it up with :meth:`increase_account_budget`.
        """
        params = dict(title=title, full_name=full_name, email=email, phone_number=phone_number,
                      country=country, city=city, legal_name=legal_name)
        if self.validate:
            _check_account_fields(params, required=True)
        return AccountInfo.from_dict(
            self._call("createAccount", params, idempotency_key=idempotency_key)
        )

    def get_account_info(self, *, account_id: str | None = None) -> AccountInfo:
        """Company details of the current account, or of ``account_id``."""
        return AccountInfo.from_dict(self._call("getAccountInfo", {"account_id": account_id}))

    def edit_account_info(
        self,
        *,
        account_id: str | None = None,
        title: str | None = None,
        full_name: str | None = None,
        email: str | None = None,
        phone_number: str | None = None,
        country: str | None = None,
        city: str | None = None,
        legal_name: str | None = None,
    ) -> AccountInfo:
        """Change company details.  Only the fields you pass are changed."""
        params = dict(title=title, full_name=full_name, email=email, phone_number=phone_number,
                      country=country, city=city, legal_name=legal_name)
        if self.validate:
            _check_account_fields(params, required=False)
        params["account_id"] = account_id
        return AccountInfo.from_dict(self._call("editAccountInfo", params))

    def get_related_accounts_list(
        self, *, offset: int | None = None, limit: int | None = None
    ) -> RelatedAccountsList:
        """Related accounts — all of them unless ``limit`` is given."""
        return RelatedAccountsList.from_dict(
            self._call("getRelatedAccountsList", {"offset": offset, "limit": limit})
        )

    def iter_related_accounts(self, *, page_size: int = 100) -> Iterator[Account]:
        """Every related account, a page at a time."""
        return _paginate_by_count(
            lambda offset: self.get_related_accounts_list(offset=offset, limit=page_size),
            "accounts",
        )

    # ------------------------------------------------------------------ #
    # Account budgets and transactions
    # ------------------------------------------------------------------ #

    def increase_account_budget(
        self, account_id: str, amount: float, *, idempotency_key: str | None = None
    ) -> TransactionStatus:
        """Move ``amount`` from the current account's budget to a related account.

        The amount is in the related account's currency, rounded to its amount
        precision.  The transfer may still be ``in_progress`` when this
        returns; see :meth:`wait_for_transaction`.
        """
        if self.validate:
            _check_required("account_id", account_id)
            _check_positive("amount", amount)
        return TransactionStatus.from_dict(self._call(
            "increaseAccountBudget", {"account_id": account_id, "amount": amount},
            idempotency_key=idempotency_key,
        ))

    def decrease_account_budget(
        self, account_id: str, amount: float, *, idempotency_key: str | None = None
    ) -> TransactionStatus:
        """Move ``amount`` from a related account's budget back to the current account."""
        if self.validate:
            _check_required("account_id", account_id)
            _check_positive("amount", amount)
        return TransactionStatus.from_dict(self._call(
            "decreaseAccountBudget", {"account_id": account_id, "amount": amount},
            idempotency_key=idempotency_key,
        ))

    def get_transaction_status(self, transaction_id: str) -> TransactionStatus:
        """The state of a budget transfer."""
        if self.validate:
            _check_required("transaction_id", transaction_id)
        return TransactionStatus.from_dict(
            self._call("getTransactionStatus", {"transaction_id": transaction_id})
        )

    def wait_for_transaction(
        self,
        transaction: str | TransactionStatus,
        *,
        timeout: float = 60.0,
        interval: float = 2.0,
    ) -> TransactionStatus:
        """Poll a transfer until it is no longer ``in_progress``.

        Returns the final :class:`~telead.models.TransactionStatus` — check
        :attr:`~telead.models.TransactionStatus.is_failed`.  Raises
        :class:`TimeoutError` if it is still in progress after ``timeout``.
        """
        status = transaction if isinstance(transaction, TransactionStatus) else None
        transaction_id = status.transaction_id if status else str(transaction)
        deadline = time.monotonic() + timeout
        while True:
            if status is None or status.is_pending:
                status = self.get_transaction_status(transaction_id)
            if not status.is_pending:
                return status
            if time.monotonic() + interval > deadline:
                raise TimeoutError(
                    f"Transaction {transaction_id} is still in progress after {timeout:g}s."
                )
            time.sleep(interval)
            status = None

    def get_account_transactions_list(
        self,
        *,
        account_id: str | None = None,
        offset: int | str | None = None,
        limit: int | None = None,
    ) -> AccountTransactionsList:
        """A page of the account's transactions (100 by default)."""
        return AccountTransactionsList.from_dict(self._call(
            "getAccountTransactionsList",
            {"account_id": account_id, "offset": offset, "limit": limit},
        ))

    def iter_account_transactions(
        self, *, account_id: str | None = None, page_size: int = _limits.LIST_LIMIT_DEFAULT
    ) -> Iterator[AccountTransaction]:
        """Every transaction of the account, following ``next_offset``."""
        return _paginate_by_offset(
            lambda offset: self.get_account_transactions_list(
                account_id=account_id, offset=offset, limit=page_size),
            "transactions",
        )

    # ------------------------------------------------------------------ #
    # Account stats and reports
    # ------------------------------------------------------------------ #

    def get_account_stats(
        self,
        from_time: int | datetime | date,
        to_time: int | datetime | date,
        interval: int = 86400,
        *,
        account_id: str | None = None,
    ) -> list[AdStatItem]:
        """Account-wide stats per interval, over ``[from_time, to_time)``.

        ``interval`` is ``300`` (5 minutes) or ``86400`` (1 day); the period
        may span at most 1000 intervals.  Times are Unix seconds, or aware
        ``datetime``/``date`` objects (dates are midnight UTC).
        """
        params = _stats_params(from_time, to_time, interval, self.validate)
        params["account_id"] = account_id
        return _list_of(AdStatItem, self._call("getAccountStats", params))

    def get_account_report(
        self, year: int, month: int, *, account_id: str | None = None
    ) -> list[AccountReportItem]:
        """Per-ad totals for one calendar month."""
        if self.validate:
            low, high = _limits.REPORT_YEAR_RANGE
            _check_int_range("year", year, low, high)
            _check_int_range("month", month, 1, 12)
        return _list_of(AccountReportItem, self._call(
            "getAccountReport", {"account_id": account_id, "year": year, "month": month},
        ))

    # ------------------------------------------------------------------ #
    # Uploads
    # ------------------------------------------------------------------ #

    def upload_ad_photo(
        self, file: Any, *, filename: str | None = None, account_id: str | None = None
    ) -> AdPhoto:
        """Upload a photo to show in ads: JPEG or PNG, ≤ 5 MB, ≥ 640 px wide, 16:9.

        ``file`` is a path, ``bytes``, or a binary file object.  Use the
        returned ``photo_id`` in :meth:`create_ad` / :meth:`edit_ad`.
        """
        return AdPhoto.from_dict(self._upload("uploadAdPhoto", file, filename, account_id))

    def upload_ad_video(
        self, file: Any, *, filename: str | None = None, account_id: str | None = None
    ) -> AdVideo:
        """Upload a video to show in ads: MP4, ≤ 20 MB, ≥ 640 px wide, 16:9, 3–60 s."""
        return AdVideo.from_dict(self._upload("uploadAdVideo", file, filename, account_id))

    def upload_website_photo(
        self, file: Any, *, filename: str | None = None, account_id: str | None = None
    ) -> WebsitePhoto:
        """Upload a photo of a promoted website: JPEG or PNG, ≤ 1 MB, ≥ 150 × 150 px."""
        return WebsitePhoto.from_dict(
            self._upload("uploadWebsitePhoto", file, filename, account_id)
        )

    # ------------------------------------------------------------------ #
    # Ads
    # ------------------------------------------------------------------ #

    def create_ad(
        self,
        *,
        title: str,
        promote_url: str,
        cpm: float,
        target: Any,
        placement: str | None = None,
        text: str | None = None,
        photo_id: str | None = None,
        video_id: str | None = None,
        impression_frequency: int | None = None,
        website_name: str | None = None,
        website_photo_id: str | None = None,
        button: str | None = None,
        conversion_event_id: str | None = None,
        additional_info: str | None = None,
        show_userpic: bool | None = None,
        initial_budget: float | None = None,
        daily_budget_limit: float | None = None,
        is_paused: bool | None = None,
        activate_date: int | datetime | None = None,
        deactivate_date: int | datetime | None = None,
        schedule: InputAdSchedule | Mapping[str, Any] | None = None,
        return_target: bool | None = None,
        account_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Ad:
        """Create an ad.

        ::

            ad = client.create_ad(
                title="Autumn launch",
                text="Everything you need to know, in one channel.",
                promote_url="https://t.me/mychannel",
                cpm=2.5,
                placement="channel_post",
                target=InputAdTargetChannels(channel_ids=["@durov"]),
                initial_budget=50,
            )

        Args:
            title: Internal name, 1–128 bytes; never shown to users.
            promote_url: The link the button opens — a channel, post, bot or
                website, up to 256 characters.
            cpm: Price per 1000 impressions, in the account's currency.
            target: An ``InputAdTarget*`` object, or its ``dict`` form.
            placement: ``channel_post``, ``bot_banner``, ``search_result`` or
                ``video_banner``.  Pass it: the API still infers it from the
                target when omitted, but says that may change.
            text: What the audience sees, 1–160 characters.  Required for
                every target type except ``search``.
            photo_id, video_id: From :meth:`upload_ad_photo` /
                :meth:`upload_ad_video`; at most one; channels and users
                targeting only.
            initial_budget: Moved from the account budget into the ad.  An ad
                with an empty budget is not submitted for review.
            is_paused: Create it on hold.  Ignored when ``activate_date`` or
                ``deactivate_date`` is passed.
            schedule: An :class:`~telead.InputAdSchedule` or its ``dict``.
            return_target: Include the target in the returned :class:`Ad`.

        The remaining arguments match the API's parameters one to one; see
        the *Ads* guide.
        """
        target_data = serialize(target)
        if self.validate:
            if target is None:
                raise ValidationError("target is required.")
            validate_input(target)
            _check_target_dict(target_data)
            _check_bytes("title", title, 1, _limits.AD_TITLE_MAX_BYTES)
            _check_chars("promote_url", promote_url, 1, _limits.PROMOTE_URL_MAX)
            _check_positive("cpm", cpm)
            if text is None:
                if target_data.get("type") != "search":
                    raise ValidationError("text is required for every target type except search.")
            _check_placement(placement)
            _check_ad_fields(
                text=text, photo_id=photo_id, video_id=video_id,
                impression_frequency=impression_frequency, website_name=website_name,
                button=button, additional_info=additional_info,
                daily_budget_limit=daily_budget_limit, schedule=schedule,
            )
            if initial_budget is not None:
                _check_non_negative("initial_budget", initial_budget)

        params: dict[str, Any] = {
            "account_id": account_id,
            "title": title,
            "text": text,
            "photo_id": photo_id,
            "video_id": video_id,
            "promote_url": promote_url,
            "cpm": cpm,
            "placement": placement,
            "target": target_data,
            "impression_frequency": impression_frequency,
            "website_name": website_name,
            "website_photo_id": website_photo_id,
            "button": button,
            "conversion_event_id": conversion_event_id,
            "additional_info": additional_info,
            "show_userpic": show_userpic,
            "initial_budget": initial_budget,
            "daily_budget_limit": daily_budget_limit,
            "is_paused": is_paused,
            "activate_date": _unix(activate_date),
            "deactivate_date": _unix(deactivate_date),
            "schedule": serialize(schedule),
            "return_target": return_target,
        }
        return Ad.from_dict(self._call("createAd", params, idempotency_key=idempotency_key))

    def edit_ad(
        self,
        ad_id: int,
        *,
        title: str | None = None,
        text: str | None = None,
        photo_id: str | None = None,
        video_id: str | None = None,
        promote_url: str | None = None,
        cpm: float | None = None,
        impression_frequency: int | None = None,
        website_name: str | None = None,
        website_photo_id: str | None = None,
        button: str | None = None,
        conversion_event_id: str | None = None,
        additional_info: str | None = None,
        show_userpic: bool | None = None,
        daily_budget_limit: float | None = None,
        is_paused: bool | None = None,
        activate_date: int | datetime | None = None,
        deactivate_date: int | datetime | None = None,
        schedule: InputAdSchedule | Mapping[str, Any] | bool | None = None,
        return_target: bool | None = None,
        account_id: str | None = None,
    ) -> Ad:
        """Change an ad.  Only the fields you pass are changed.

        * A new ``photo_id`` or ``video_id`` replaces any existing media.
        * ``conversion_event_id`` and ``additional_info`` cannot be changed
          once set.
        * ``is_paused`` pauses (``True``) or resumes (``False``) and clears
          any ``activate_date``/``deactivate_date``.
        * ``schedule=False`` removes the schedule.
        * ``daily_budget_limit=0`` removes the daily limit.
        """
        if self.validate:
            _check_ad_id(ad_id)
            if title is not None:
                _check_bytes("title", title, 1, _limits.AD_TITLE_MAX_BYTES)
            if promote_url is not None:
                _check_chars("promote_url", promote_url, 1, _limits.PROMOTE_URL_MAX)
            if cpm is not None:
                _check_positive("cpm", cpm)
            _check_ad_fields(
                text=text, photo_id=photo_id, video_id=video_id,
                impression_frequency=impression_frequency, website_name=website_name,
                button=button, additional_info=additional_info,
                daily_budget_limit=daily_budget_limit,
                schedule=None if schedule is False else schedule,
            )
            if schedule is True:
                raise ValidationError("schedule=True is not meaningful; pass a schedule, or False to remove it.")

        params: dict[str, Any] = {
            "account_id": account_id,
            "ad_id": ad_id,
            "title": title,
            "text": text,
            "photo_id": photo_id,
            "video_id": video_id,
            "promote_url": promote_url,
            "cpm": cpm,
            "impression_frequency": impression_frequency,
            "website_name": website_name,
            "website_photo_id": website_photo_id,
            "button": button,
            "conversion_event_id": conversion_event_id,
            "additional_info": additional_info,
            "show_userpic": show_userpic,
            "daily_budget_limit": daily_budget_limit,
            "is_paused": is_paused,
            "activate_date": _unix(activate_date),
            "deactivate_date": _unix(deactivate_date),
            "schedule": serialize(schedule),
            "return_target": return_target,
        }
        return Ad.from_dict(self._call("editAd", params))

    def pause_ad(self, ad_id: int, *, account_id: str | None = None) -> Ad:
        """Put an ad on hold.  Same as ``edit_ad(ad_id, is_paused=True)``."""
        return self.edit_ad(ad_id, is_paused=True, account_id=account_id)

    def resume_ad(self, ad_id: int, *, account_id: str | None = None) -> Ad:
        """Resume a paused ad.  Same as ``edit_ad(ad_id, is_paused=False)``."""
        return self.edit_ad(ad_id, is_paused=False, account_id=account_id)

    def increase_ad_budget(
        self,
        ad_id: int,
        amount: float,
        *,
        return_target: bool | None = None,
        account_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Ad:
        """Move ``amount`` from the account budget into the ad's budget."""
        if self.validate:
            _check_ad_id(ad_id)
            _check_positive("amount", amount)
        return Ad.from_dict(self._call(
            "increaseAdBudget",
            {"account_id": account_id, "ad_id": ad_id, "amount": amount,
             "return_target": return_target},
            idempotency_key=idempotency_key,
        ))

    def decrease_ad_budget(
        self,
        ad_id: int,
        amount: float,
        *,
        return_target: bool | None = None,
        account_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Ad:
        """Move ``amount`` from the ad's budget back to the account budget.

        The ad must have been inactive for at least 10 minutes.
        """
        if self.validate:
            _check_ad_id(ad_id)
            _check_positive("amount", amount)
        return Ad.from_dict(self._call(
            "decreaseAdBudget",
            {"account_id": account_id, "ad_id": ad_id, "amount": amount,
             "return_target": return_target},
            idempotency_key=idempotency_key,
        ))

    def submit_ad_for_review(
        self, ad_id: int, *, return_target: bool | None = None, account_id: str | None = None
    ) -> Ad:
        """Submit an ad whose status is ``ready_for_review``.

        Ads with a budget are submitted automatically when created or edited;
        this is for the ones that were not.
        """
        if self.validate:
            _check_ad_id(ad_id)
        return Ad.from_dict(self._call(
            "submitAdForReview",
            {"account_id": account_id, "ad_id": ad_id, "return_target": return_target},
        ))

    def delete_ad(self, ad_id: int, *, account_id: str | None = None) -> bool:
        """Delete an ad.  It must have been inactive for at least 10 minutes."""
        if self.validate:
            _check_ad_id(ad_id)
        return bool(self._call("deleteAd", {"account_id": account_id, "ad_id": ad_id}))

    def get_ads_by_id(
        self,
        ad_ids: Iterable[int],
        *,
        return_target: bool | None = None,
        account_id: str | None = None,
    ) -> list[Ad]:
        """Ads by identifier."""
        ids = _as_list(ad_ids)
        if self.validate and not ids:
            raise ValidationError("ad_ids must not be empty.")
        return _list_of(Ad, self._call(
            "getAdsById",
            {"account_id": account_id, "ad_ids": ids, "return_target": return_target},
        ))

    def get_ad(
        self, ad_id: int, *, return_target: bool | None = None, account_id: str | None = None
    ) -> Ad | None:
        """One ad by identifier, or ``None`` if the API returned nothing for it."""
        ads = self.get_ads_by_id([ad_id], return_target=return_target, account_id=account_id)
        return ads[0] if ads else None

    def get_ads_list(
        self,
        *,
        offset: str | None = None,
        limit: int | None = None,
        return_target: bool | None = None,
        account_id: str | None = None,
    ) -> AdList:
        """A page of the account's ads (up to 100).  Follow ``next_offset`` for more."""
        if self.validate and limit is not None:
            _check_int_range("limit", limit, 0, _limits.ADS_LIST_LIMIT_MAX)
        return AdList.from_dict(self._call(
            "getAdsList",
            {"account_id": account_id, "offset": offset, "limit": limit,
             "return_target": return_target},
        ))

    def iter_ads(
        self,
        *,
        return_target: bool | None = None,
        account_id: str | None = None,
        page_size: int = _limits.ADS_LIST_LIMIT_MAX,
    ) -> Iterator[Ad]:
        """Every ad of the account, following ``next_offset``."""
        return _paginate_by_offset(
            lambda offset: self.get_ads_list(
                offset=offset, limit=page_size, return_target=return_target,
                account_id=account_id),
            "ads",
        )

    def get_ad_transactions_list(
        self,
        ad_id: int,
        *,
        offset: int | str | None = None,
        limit: int | None = None,
        account_id: str | None = None,
    ) -> AdTransactionsList:
        """A page of an ad's transactions (100 by default)."""
        if self.validate:
            _check_ad_id(ad_id)
        return AdTransactionsList.from_dict(self._call(
            "getAdTransactionsList",
            {"account_id": account_id, "ad_id": ad_id, "offset": offset, "limit": limit},
        ))

    def iter_ad_transactions(
        self, ad_id: int, *, account_id: str | None = None,
        page_size: int = _limits.LIST_LIMIT_DEFAULT,
    ) -> Iterator[AdTransaction]:
        """Every transaction of an ad, following ``next_offset``."""
        return _paginate_by_offset(
            lambda offset: self.get_ad_transactions_list(
                ad_id, offset=offset, limit=page_size, account_id=account_id),
            "transactions",
        )

    def get_ad_stats(
        self,
        ad_id: int,
        from_time: int | datetime | date,
        to_time: int | datetime | date,
        interval: int = 86400,
        *,
        account_id: str | None = None,
    ) -> list[AdStatItem]:
        """An ad's stats per interval, over ``[from_time, to_time)``.

        Same time rules as :meth:`get_account_stats`.
        """
        if self.validate:
            _check_ad_id(ad_id)
        params = _stats_params(from_time, to_time, interval, self.validate)
        params.update(account_id=account_id, ad_id=ad_id)
        return _list_of(AdStatItem, self._call("getAdStats", params))

    # ------------------------------------------------------------------ #
    # Audiences
    # ------------------------------------------------------------------ #

    def create_audience(
        self,
        title: str,
        phones: Iterable[str] | None = None,
        *,
        account_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Audience:
        """Create a retargeting audience from phone numbers or their SHA-256 hashes.

        One API call takes up to 10,000 numbers.  Pass more and the rest are
        added with :meth:`add_audience_phones` in batches after the audience
        is created (up to 1,000,000 in total).
        """
        numbers = _as_list(phones or [])
        if self.validate:
            _check_chars("title", title, 1, _limits.AUDIENCE_TITLE_MAX)
            _check_phones(numbers, _limits.AUDIENCE_PHONES_MAX)
        first, rest = numbers[:_limits.AUDIENCE_PHONES_PER_CALL], \
            numbers[_limits.AUDIENCE_PHONES_PER_CALL:]
        audience = Audience.from_dict(self._call(
            "createAudience",
            {"account_id": account_id, "title": title, "add_phones": first or None},
            idempotency_key=idempotency_key,
        ))
        if rest:
            audience = self.add_audience_phones(audience.audience_id, rest, account_id=account_id)
        return audience

    def edit_audience(
        self,
        audience_id: int,
        *,
        title: str | None = None,
        add_phones: Iterable[str] | None = None,
        remove_phones: Iterable[str] | None = None,
        reset_phones: bool | None = None,
        account_id: str | None = None,
    ) -> Audience:
        """Rename an audience and add, remove or reset its numbers — in one call.

        Removals (or the reset) happen before additions.  ``remove_phones``
        is ignored when ``reset_phones`` is set.  Each list takes at most
        10,000 numbers; see :meth:`add_audience_phones` for more.
        """
        add = _as_list(add_phones) if add_phones is not None else None
        remove = _as_list(remove_phones) if remove_phones is not None else None
        if self.validate:
            _check_int("audience_id", audience_id)
            if title is not None:
                _check_bytes("title", title, 1, _limits.AUDIENCE_TITLE_MAX)
            if add is not None:
                _check_phones(add, _limits.AUDIENCE_PHONES_PER_CALL)
            if remove is not None:
                _check_phones(remove, _limits.AUDIENCE_PHONES_PER_CALL)
        return Audience.from_dict(self._call("editAudience", {
            "account_id": account_id,
            "audience_id": audience_id,
            "title": title,
            "add_phones": add,
            "remove_phones": remove,
            "reset_phones": reset_phones,
        }))

    def add_audience_phones(
        self,
        audience_id: int,
        phones: Iterable[str],
        *,
        batch_size: int = _limits.AUDIENCE_PHONES_PER_CALL,
        account_id: str | None = None,
    ) -> Audience:
        """Add any number of phones, ``batch_size`` per call.  Returns the audience
        as of the last batch."""
        return self._audience_batches(audience_id, phones, "add_phones", batch_size, account_id)

    def remove_audience_phones(
        self,
        audience_id: int,
        phones: Iterable[str],
        *,
        batch_size: int = _limits.AUDIENCE_PHONES_PER_CALL,
        account_id: str | None = None,
    ) -> Audience:
        """Remove any number of phones, ``batch_size`` per call."""
        return self._audience_batches(audience_id, phones, "remove_phones", batch_size, account_id)

    def delete_audience(self, audience_id: int, *, account_id: str | None = None) -> bool:
        """Delete an audience that no ad uses."""
        if self.validate:
            _check_int("audience_id", audience_id)
        return bool(self._call(
            "deleteAudience", {"account_id": account_id, "audience_id": audience_id}
        ))

    def get_audiences_by_id(
        self, audience_ids: Iterable[int], *, account_id: str | None = None
    ) -> list[Audience]:
        """Audiences by identifier."""
        ids = _as_list(audience_ids)
        if self.validate and not ids:
            raise ValidationError("audience_ids must not be empty.")
        return _list_of(Audience, self._call(
            "getAudiencesById", {"account_id": account_id, "audience_ids": ids}
        ))

    def get_audiences_list(
        self,
        *,
        offset: int | None = None,
        limit: int | None = None,
        account_id: str | None = None,
    ) -> AudiencesList:
        """The account's audiences — all of them unless ``limit`` is given."""
        return AudiencesList.from_dict(self._call(
            "getAudiencesList", {"account_id": account_id, "offset": offset, "limit": limit}
        ))

    # ------------------------------------------------------------------ #
    # Pixel
    # ------------------------------------------------------------------ #

    def create_pixel(
        self, *, account_id: str | None = None, idempotency_key: str | None = None
    ) -> Pixel:
        """Create the account's Pixel Tag."""
        return Pixel.from_dict(self._call(
            "createPixel", {"account_id": account_id}, idempotency_key=idempotency_key
        ))

    def get_pixel(self, *, account_id: str | None = None) -> Pixel:
        """The account's Pixel Tag and its base code snippet."""
        return Pixel.from_dict(self._call("getPixel", {"account_id": account_id}))

    def create_pixel_event(
        self,
        title: str,
        type: str,
        *,
        account_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> PixelEvent:
        """Create a conversion event — ``type`` is ``purchase``, ``lead``, … or ``custom``."""
        if self.validate:
            _check_chars("title", title, 1, _limits.PIXEL_EVENT_TITLE_MAX)
            _check_choice("type", type, _limits.PIXEL_EVENT_TYPES)
        return PixelEvent.from_dict(self._call(
            "createPixelEvent", {"account_id": account_id, "title": title, "type": type},
            idempotency_key=idempotency_key,
        ))

    def edit_pixel_event(
        self, event_id: str, title: str, *, account_id: str | None = None
    ) -> PixelEvent:
        """Rename a pixel event.  Automatically created events cannot be edited."""
        if self.validate:
            _check_required("event_id", event_id)
            _check_bytes("title", title, 1, _limits.PIXEL_EVENT_TITLE_MAX)
        return PixelEvent.from_dict(self._call(
            "editPixelEvent", {"account_id": account_id, "event_id": event_id, "title": title}
        ))

    def delete_pixel_event(self, event_id: str, *, account_id: str | None = None) -> bool:
        """Delete a pixel event that no ad uses and that was not created automatically."""
        if self.validate:
            _check_required("event_id", event_id)
        return bool(self._call(
            "deletePixelEvent", {"account_id": account_id, "event_id": event_id}
        ))

    def get_pixel_events_by_id(
        self, event_ids: Iterable[str], *, account_id: str | None = None
    ) -> list[PixelEvent]:
        """Pixel events by identifier."""
        ids = _as_list(event_ids)
        if self.validate and not ids:
            raise ValidationError("event_ids must not be empty.")
        return _list_of(PixelEvent, self._call(
            "getPixelEventsById", {"account_id": account_id, "event_ids": ids}
        ))

    def get_pixel_events_list(
        self,
        *,
        offset: int | None = None,
        limit: int | None = None,
        account_id: str | None = None,
    ) -> PixelEventsList:
        """The account's pixel events — all of them unless ``limit`` is given."""
        return PixelEventsList.from_dict(self._call(
            "getPixelEventsList", {"account_id": account_id, "offset": offset, "limit": limit}
        ))

    # ------------------------------------------------------------------ #
    # Targeting catalogue
    # ------------------------------------------------------------------ #

    def get_target_languages_list(self) -> list[TargetLanguage]:
        """Languages you can target, with their IETF tags."""
        return _list_of(TargetLanguage, self._call("getTargetLanguagesList", {}))

    def get_target_topics_list(self) -> list[TargetTopic]:
        """Topics you can target, with their ids."""
        return _list_of(TargetTopic, self._call("getTargetTopicsList", {}))

    def get_target_countries_list(self) -> list[TargetCountry]:
        """Countries you can target, with their ISO codes."""
        return _list_of(TargetCountry, self._call("getTargetCountriesList", {}))

    def get_target_locations_by_id(self, location_ids: Iterable[int]) -> list[TargetLocation]:
        """Locations by identifier."""
        ids = _as_list(location_ids)
        if self.validate and not ids:
            raise ValidationError("location_ids must not be empty.")
        return _list_of(TargetLocation, self._call(
            "getTargetLocationsById", {"location_ids": ids}
        ))

    def get_target_locations_list(
        self,
        country_code: str,
        query: str,
        *,
        offset: str | None = None,
        limit: int | None = None,
    ) -> TargetLocationList:
        """Search one country's locations by name (100 per page by default)."""
        if self.validate:
            if not isinstance(country_code, str) or len(country_code) != 2:
                raise ValidationError(
                    f"country_code must be a two-letter ISO code, got {country_code!r}."
                )
            _check_required("query", query)
        return TargetLocationList.from_dict(self._call(
            "getTargetLocationsList",
            {"country_code": country_code, "query": query, "offset": offset, "limit": limit},
        ))

    def iter_target_locations(
        self, country_code: str, query: str, *, page_size: int = _limits.LIST_LIMIT_DEFAULT
    ) -> Iterator[TargetLocation]:
        """Every location matching ``query``, following ``next_offset``."""
        return _paginate_by_offset(
            lambda offset: self.get_target_locations_list(
                country_code, query, offset=offset, limit=page_size),
            "locations",
        )

    def get_target_channel(self, channel: int | str, *, for_excluding: bool | None = None) -> TargetChannel:
        """Resolve a channel for targeting.

        Pass ``"@username"``.  A numeric id only works once this account has
        resolved that channel by username; after that both forms are accepted.
        Set ``for_excluding=True`` when you mean to exclude it.
        """
        if self.validate:
            _check_peer("channel", channel)
        return TargetChannel.from_dict(self._call(
            "getTargetChannel", {"channel_id": channel, "for_excluding": for_excluding}
        ))

    def get_target_bot(self, bot: int | str) -> TargetBot:
        """Resolve a bot for targeting.  Same rules as :meth:`get_target_channel`."""
        if self.validate:
            _check_peer("bot", bot)
        return TargetBot.from_dict(self._call("getTargetBot", {"bot_id": bot}))

    # ------------------------------------------------------------------ #
    # Accounts, as a view
    # ------------------------------------------------------------------ #

    def with_account(self, account_id: str | None) -> "Client":
        """A client for the same token that acts on ``account_id`` by default.

        It shares this client's connection and settings::

            for account in client.iter_related_accounts():
                sub = client.with_account(account.account_id)
                for ad in sub.iter_ads():
                    ...

        Closing the view does not close the shared connection.
        """
        view = Client(
            self.token,
            account_id=account_id,
            base_url=self.base_url,
            timeout=self.timeout,
            max_retries=self.max_retries,
            backoff_base=self.backoff_base,
            backoff_max=self.backoff_max,
            auto_idempotency=self.auto_idempotency,
            validate=self.validate,
            session=self._session,
            user_agent=self._user_agent,
        )
        return view

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def close(self) -> None:
        """Close the underlying HTTP session, if this client created it."""
        if self._owns_session:
            self._session.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        scope = f" account_id={self.account_id!r}" if self.account_id else ""
        return f"<{type(self).__name__} base_url={self.base_url!r}{scope}>"

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _audience_batches(
        self, audience_id: int, phones: Iterable[str], field_name: str,
        batch_size: int, account_id: str | None,
    ) -> Audience:
        numbers = _as_list(phones)
        batch_size = max(1, min(int(batch_size), _limits.AUDIENCE_PHONES_PER_CALL))
        if not numbers:
            raise ValidationError("phones must not be empty.")
        audience: Audience | None = None
        for start in range(0, len(numbers), batch_size):
            audience = self.edit_audience(
                audience_id, account_id=account_id,
                **{field_name: numbers[start:start + batch_size]},
            )
        return audience  # type: ignore[return-value]

    def _upload(self, method: str, file: Any, filename: str | None,
                account_id: str | None) -> Any:
        content, guessed = _read_file(file)
        filename = filename or guessed or "upload"
        mime_type = _guess_mime(filename, content)
        if self.validate:
            _check_upload(method, filename, mime_type, content)
        return self._call(
            method, {"account_id": account_id},
            files={"file": (filename, content, mime_type or "application/octet-stream")},
        )

    def _call(
        self,
        method: str,
        params: dict[str, Any],
        *,
        files: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        """Perform an API call with idempotency keys and retries; return ``result``."""
        if method in _SCOPED_METHODS and params.get("account_id") is None and self.account_id:
            params["account_id"] = self.account_id
        params = {k: serialize(v) for k, v in params.items() if v is not None}

        headers: dict[str, str] = {}
        if idempotency_key is None and "idempotency_key" in params:
            idempotency_key = str(params.pop("idempotency_key"))
        if idempotency_key is None and self.auto_idempotency and method in _limits.IDEMPOTENT_METHODS:
            idempotency_key = uuid.uuid4().hex
        if idempotency_key is not None:
            if self.validate and len(idempotency_key) > _limits.IDEMPOTENCY_KEY_MAX:
                raise ValidationError(
                    f"idempotency_key is {len(idempotency_key)} characters; "
                    f"the limit is {_limits.IDEMPOTENCY_KEY_MAX}."
                )
            headers["Idempotency-Key"] = idempotency_key

        # A repeat is harmless for reads, for absolute-state edits, and for any
        # call carrying an idempotency key (the API replays the first result).
        repeatable = (
            method.startswith("get")
            or method in _REPEATABLE_WRITES
            or idempotency_key is not None
        )

        if files:
            # multipart/form-data: every non-file field is a string, and lists
            # and objects are sent JSON-serialized, as the docs describe.
            request_kwargs: dict[str, Any] = {
                "data": {k: _form_value(v) for k, v in params.items()},
                "files": dict(files),
            }
            read_timeout = max(self.timeout, 120.0)
        else:
            request_kwargs = {"json": params}
            read_timeout = self.timeout

        url = f"{self.base_url}/{method}"
        attempt = 0
        while True:
            try:
                response = self._send(url, headers=headers, read_timeout=read_timeout,
                                      **request_kwargs)
            except TransportError:
                if not repeatable or attempt >= self.max_retries:
                    raise
                self._sleep_backoff(attempt)
                attempt += 1
                continue

            try:
                return self._parse(method, response)
            except APIError as error:
                # A rate limit rejects the request before it runs, so it is
                # always safe to repeat; other retryable errors only when the
                # call is repeatable.
                retry = error.retryable and (repeatable or isinstance(error, RateLimitError))
                if not retry or attempt >= self.max_retries:
                    raise
                self._sleep_backoff(attempt, getattr(error, "retry_after", None),
                                    rate_limited=isinstance(error, RateLimitError))
                attempt += 1

    def _parse(self, method: str, response: Any) -> Any:
        body = _parse_body(response)
        status = response.status_code
        if isinstance(body, dict) and "ok" in body:
            if body.get("ok") is True and status < 400:
                if _header(response, "Idempotent-Replayed") == "true":
                    log.debug("%s: replayed an earlier result for this idempotency key", method)
                return body.get("result")
        raise error_from_response(status, body, getattr(response, "headers", None), method=method)

    def _send(self, url: str, *, headers: dict[str, str], read_timeout: float,
              **kwargs: Any) -> Any:
        all_headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "User-Agent": self._user_agent,
            **headers,
        }
        try:
            return self._session.request(
                "POST", url, headers=all_headers, timeout=(10.0, read_timeout), **kwargs,
            )
        except requests.RequestException as exc:  # pragma: no cover - network dependent
            raise TransportError(f"POST {url} failed: {exc}") from exc

    def _sleep_backoff(
        self, attempt: int, retry_after: float | None = None, *, rate_limited: bool = False
    ) -> None:
        if retry_after is not None:
            delay = min(retry_after, self.backoff_max)
        else:
            base = max(self.backoff_base, _RATE_LIMIT_BACKOFF_BASE) if rate_limited else self.backoff_base
            delay = min(self.backoff_max, base * (2 ** attempt))
            delay += random.uniform(0, delay * 0.1)  # jitter, to spread retries out
        time.sleep(delay)


# ---------------------------------------------------------------------- #
# Pagination
# ---------------------------------------------------------------------- #


def _paginate_by_offset(fetch: Callable[[Any], Any], items: str) -> Iterator[Any]:
    """Follow ``next_offset`` until a page comes back without one."""
    offset: Any = None
    seen_offsets: set = set()
    while True:
        page = fetch(offset)
        batch = getattr(page, items)
        yield from batch
        offset = page.next_offset
        if not offset or not batch or offset in seen_offsets:
            return
        seen_offsets.add(offset)


def _paginate_by_count(fetch: Callable[[int], Any], items: str) -> Iterator[Any]:
    """Advance a numeric ``offset`` until ``total_count`` items were read."""
    offset = 0
    while True:
        page = fetch(offset)
        batch = getattr(page, items)
        yield from batch
        offset += len(batch)
        if not batch or offset >= page.total_count:
            return


# ---------------------------------------------------------------------- #
# Conversions
# ---------------------------------------------------------------------- #


def _list_of(model: Any, result: Any) -> list:
    if not isinstance(result, list):
        return []
    return [model.from_dict(item) for item in result if isinstance(item, dict)]


def _as_list(values: Any) -> list:
    if isinstance(values, (str, bytes)):
        return [values]
    return list(values)


def _unix(value: Any) -> int | None:
    """Unix seconds from an int, an aware/naive ``datetime`` or a ``date``."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValidationError(f"Expected a time, got {value!r}.")
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return int(value.timestamp())
    if isinstance(value, date):
        return int(datetime(value.year, value.month, value.day, tzinfo=timezone.utc).timestamp())
    if isinstance(value, (int, float)):
        return int(value)
    raise ValidationError(f"Expected Unix seconds, a datetime or a date, got {value!r}.")


def _stats_params(from_time: Any, to_time: Any, interval: int, validate: bool) -> dict[str, Any]:
    start, end = _unix(from_time), _unix(to_time)
    if validate:
        if interval not in _limits.STAT_INTERVALS:
            raise ValidationError(
                f"interval must be 300 (5 minutes) or 86400 (1 day), got {interval!r}."
            )
        if end is None or start is None or end <= start:
            raise ValidationError("to_time must be after from_time.")
        if end - start > _limits.STAT_MAX_POINTS * interval:
            raise ValidationError(
                f"The period spans {(end - start) / interval:.0f} intervals; the limit is "
                f"{_limits.STAT_MAX_POINTS}.  Use a longer interval or a shorter period."
            )
    return {"from_time": start, "to_time": end, "interval": interval}


def _form_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, separators=(",", ":"))
    return str(value)


def _header(response: Any, name: str) -> str | None:
    headers = getattr(response, "headers", None) or {}
    try:
        value = headers.get(name)
    except AttributeError:
        return None
    return value.lower() if isinstance(value, str) else None


def _parse_body(response: Any) -> Any:
    try:
        return response.json()
    except Exception:
        return getattr(response, "text", "")


# ---------------------------------------------------------------------- #
# Files
# ---------------------------------------------------------------------- #


def _read_file(file: Any) -> tuple[bytes, str | None]:
    """Return ``(content, filename)`` for a path, bytes, or binary file object."""
    if isinstance(file, (str, os.PathLike)):
        path = Path(file)
        try:
            return path.read_bytes(), path.name
        except OSError as exc:
            raise ValidationError(f"Could not read {path}: {exc}") from exc
    if isinstance(file, (bytes, bytearray)):
        return bytes(file), None
    if hasattr(file, "read"):
        name = getattr(file, "name", None)
        name = Path(name).name if isinstance(name, str) else None
        content = file.read()
        if isinstance(content, str):
            raise ValidationError("Open files in binary mode ('rb').")
        return content, name
    raise ValidationError(
        f"Unsupported file input {type(file).__name__}; pass a path, bytes, or an open binary file."
    )


def _guess_mime(filename: str, content: bytes) -> str | None:
    # Magic numbers first: they cannot disagree with the file itself.
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content[4:8] == b"ftyp":
        return "video/mp4"
    guessed, _ = mimetypes.guess_type(filename)
    return guessed


# ---------------------------------------------------------------------- #
# Validation
# ---------------------------------------------------------------------- #


def _check_required(name: str, value: Any) -> None:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{name} is required.")


def _check_chars(name: str, value: Any, low: int, high: int) -> None:
    if not isinstance(value, str):
        raise ValidationError(f"{name} must be a string, got {type(value).__name__}.")
    if not low <= len(value) <= high:
        raise ValidationError(f"{name} is {len(value)} characters; it must be {low}–{high}.")


def _check_bytes(name: str, value: Any, low: int, high: int) -> None:
    if not isinstance(value, str):
        raise ValidationError(f"{name} must be a string, got {type(value).__name__}.")
    size = len(value.encode("utf-8"))
    if not low <= size <= high:
        raise ValidationError(
            f"{name} is {size} bytes in UTF-8; it must be {low}–{high} bytes."
        )


def _check_int(name: str, value: Any) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{name} must be an int, got {value!r}.")


def _check_ad_id(ad_id: Any) -> None:
    _check_int("ad_id", ad_id)


def _check_int_range(name: str, value: Any, low: int, high: int) -> None:
    _check_int(name, value)
    if not low <= value <= high:
        raise ValidationError(f"{name} must be {low}–{high}, got {value}.")


def _check_positive(name: str, value: Any) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValidationError(f"{name} must be a positive number, got {value!r}.")


def _check_non_negative(name: str, value: Any) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValidationError(f"{name} must be a number ≥ 0, got {value!r}.")


def _check_choice(name: str, value: Any, choices: Sequence[str]) -> None:
    if value not in choices:
        raise ValidationError(f"{name} must be one of {', '.join(choices)}; got {value!r}.")


def _check_placement(placement: Any) -> None:
    if placement is not None:
        _check_choice("placement", placement, _limits.PLACEMENTS)


def _check_peer(name: str, value: Any) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, str)) or value == "":
        raise ValidationError(f"{name} must be '@username' or a numeric id, got {value!r}.")


def _check_account_fields(params: dict[str, Any], *, required: bool) -> None:
    for name, (low, high) in _limits.ACCOUNT_FIELD_LIMITS.items():
        value = params.get(name)
        if value is None:
            if required and name != "legal_name":
                raise ValidationError(f"{name} is required.")
            continue
        _check_chars(name, value, low, high)
    phone = params.get("phone_number")
    if phone is None:
        if required:
            raise ValidationError("phone_number is required.")
    else:
        _check_required("phone_number", phone)


def _check_target_dict(target: Any) -> None:
    if not isinstance(target, dict):
        raise ValidationError(
            f"target must be an InputAdTarget* object or a dict, got {type(target).__name__}."
        )
    if target.get("type") not in _limits.TARGET_TYPES:
        raise ValidationError(
            f"target type must be one of {', '.join(_limits.TARGET_TYPES)}; "
            f"got {target.get('type')!r}."
        )


def _check_ad_fields(
    *,
    text: Any,
    photo_id: Any,
    video_id: Any,
    impression_frequency: Any,
    website_name: Any,
    button: Any,
    additional_info: Any,
    daily_budget_limit: Any,
    schedule: Any,
) -> None:
    if text is not None:
        _check_chars("text", text, 1, _limits.AD_TEXT_MAX)
    if photo_id is not None and video_id is not None:
        raise ValidationError("Pass photo_id or video_id, not both.")
    if impression_frequency is not None:
        low, high = _limits.IMPRESSION_FREQUENCY_RANGE
        _check_int_range("impression_frequency", impression_frequency, low, high)
    if website_name is not None:
        _check_chars("website_name", website_name, 1, _limits.WEBSITE_NAME_MAX)
    if button is not None and button != "":
        _check_choice("button", button, _limits.BUTTONS)
    if additional_info is not None:
        _check_chars("additional_info", additional_info, 0, _limits.ADDITIONAL_INFO_MAX)
    if daily_budget_limit is not None:
        _check_non_negative("daily_budget_limit", daily_budget_limit)
    if schedule is not None:
        validate_input(schedule)


def _check_phones(numbers: list, maximum: int) -> None:
    if len(numbers) > maximum:
        raise ValidationError(f"{len(numbers)} phone numbers; the limit is {maximum}.")
    for number in numbers:
        if not isinstance(number, str) or not number.strip():
            raise ValidationError(
                f"Phone numbers must be non-empty strings (numbers or SHA-256 hashes), got {number!r}."
            )


def _check_upload(method: str, filename: str, mime_type: str | None, content: bytes) -> None:
    rule = _limits.UPLOAD_LIMITS[method]
    if not content:
        raise ValidationError("Refusing to upload an empty file.")
    if len(content) > rule.max_bytes:
        raise ValidationError(
            f"{filename} is {len(content)} bytes; {method} accepts up to {rule.max_bytes} "
            f"({rule.requirements})."
        )
    if mime_type not in rule.mime_types:
        raise ValidationError(
            f"{filename} does not look like {' or '.join(rule.mime_types)}; "
            f"{method} accepts {rule.requirements}."
        )
