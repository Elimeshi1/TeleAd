"""Typed views over the JSON the API returns.

Every model keeps the payload it was parsed from in ``raw``, so fields added
to the platform later are still reachable without a library upgrade.
Optional fields the API left out are ``None``.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, ClassVar, Dict, Iterator, List, Optional, Union

from .limits import CURRENCIES, Currency

__all__ = [
    "Account",
    "AccountInfo",
    "RelatedAccountsList",
    "TransactionStatus",
    "AccountTransaction",
    "AccountTransactionsList",
    "AccountTransactionPeer",
    "AccountTransactionPeerExternal",
    "AccountTransactionPeerMainAccount",
    "AccountTransactionPeerRelatedAccount",
    "AccountTransactionPeerAd",
    "AccountReportItem",
    "AdPhoto",
    "AdVideo",
    "WebsitePhoto",
    "AdSchedule",
    "DeclineReason",
    "Ad",
    "AdList",
    "AdTarget",
    "AdTargetChannels",
    "AdTargetUsers",
    "AdTargetBots",
    "AdTargetSearch",
    "AdTransaction",
    "AdTransactionsList",
    "AdTransactionPeer",
    "AdTransactionPeerAccount",
    "AdTransactionPeerViews",
    "AdStatItem",
    "Audience",
    "AudiencesList",
    "Pixel",
    "PixelEvent",
    "PixelEventsList",
    "TargetLanguage",
    "TargetTopic",
    "TargetCountry",
    "TargetLocation",
    "TargetLocationList",
    "TargetChannel",
    "TargetBot",
    "UnknownObject",
]


# ---------------------------------------------------------------------- #
# Parsing helpers
# ---------------------------------------------------------------------- #


def _dt(timestamp: Any) -> datetime | None:
    if timestamp is None or isinstance(timestamp, bool):
        return None
    try:
        return datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _one(parser: Callable[[Any], Any]) -> Callable[[Any], Any]:
    return lambda value: parser(value) if isinstance(value, dict) else None


def _many(parser: Callable[[Any], Any]) -> Callable[[Any], Any]:
    return lambda value: [parser(item) for item in value if isinstance(item, dict)] \
        if isinstance(value, list) else []


class _Model:
    """Builds a dataclass from a dict by field name.

    ``_nested`` maps a field to a parser for its value; ``_aliases`` maps a
    field to older names the API still sends.
    """

    _nested: ClassVar[Dict[str, Callable[[Any], Any]]] = {}
    _aliases: ClassVar[Dict[str, tuple]] = {}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Any:
        if not isinstance(data, dict):
            data = {}
        kwargs: dict[str, Any] = {}
        for f in dataclasses.fields(cls):  # type: ignore[arg-type]
            if f.name == "raw":
                continue
            value = data.get(f.name)
            if value is None:
                for alias in cls._aliases.get(f.name, ()):
                    if data.get(alias) is not None:
                        value = data[alias]
                        break
            parser = cls._nested.get(f.name)
            if parser is not None:
                value = parser(value)
            if value is None and f.default is not dataclasses.MISSING:
                value = f.default
            elif value is None and f.default_factory is not dataclasses.MISSING:  # type: ignore[misc]
                value = f.default_factory()  # type: ignore[misc]
            kwargs[f.name] = value
        return cls(raw=data, **kwargs)  # type: ignore[call-arg]


class _HasCurrency:
    currency: Optional[str]

    @property
    def currency_info(self) -> Currency | None:
        """Precision rules for :attr:`currency`, or ``None`` if unknown."""
        return CURRENCIES.get(self.currency or "")


@dataclass(frozen=True)
class UnknownObject(_Model):
    """A variant (peer, target) whose ``type`` this library does not know yet."""

    type: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


# ---------------------------------------------------------------------- #
# Accounts
# ---------------------------------------------------------------------- #


@dataclass(frozen=True)
class Account(_Model, _HasCurrency):
    """An advertiser account and its balances."""

    account_id: str = ""
    title: str = ""
    currency: Optional[str] = None
    spent_budget: float = 0.0
    remaining_budget: float = 0.0
    #: Money already moved into ads' own budgets.
    ads_budget: float = 0.0
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class AccountInfo(_Model):
    """The company details of an account."""

    account_id: str = ""
    title: str = ""
    full_name: str = ""
    email: str = ""
    phone_number: str = ""
    country: str = ""
    city: str = ""
    legal_name: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class RelatedAccountsList(_Model):
    """A page of related accounts."""

    total_count: int = 0
    accounts: List[Account] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    _nested = {"accounts": _many(Account.from_dict)}

    def __iter__(self) -> Iterator[Account]:
        return iter(self.accounts)

    def __len__(self) -> int:
        return len(self.accounts)


@dataclass(frozen=True)
class TransactionStatus(_Model, _HasCurrency):
    """The state of a transfer between the main account and a related one."""

    transaction_id: str = ""
    #: ``"in_progress"``, ``"failed"`` or ``"completed"``.
    status: str = ""
    currency: Optional[str] = None
    #: Negative when money was withdrawn from the related account.
    amount: float = 0.0
    main_account: Optional[Account] = None
    related_account: Optional[Account] = None
    #: Why a failed transaction failed, for example ``"NOT_ENOUGH_BUDGET"``.
    error: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    _nested = {
        "main_account": _one(Account.from_dict),
        "related_account": _one(Account.from_dict),
    }

    @property
    def is_completed(self) -> bool:
        return self.status == "completed"

    @property
    def is_failed(self) -> bool:
        return self.status == "failed"

    @property
    def is_pending(self) -> bool:
        return self.status == "in_progress"


@dataclass(frozen=True)
class AccountTransactionPeerExternal(_Model):
    """Money from outside Telegram Ads — a top-up."""

    type: str = "external"
    #: For example an invoice number.
    comment: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class AccountTransactionPeerMainAccount(_Model):
    """The main account this related account belongs to."""

    type: str = "main_account"
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class AccountTransactionPeerRelatedAccount(_Model):
    """A related account of this one."""

    type: str = "related_account"
    account_id: str = ""
    account_title: str = ""
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class AccountTransactionPeerAd(_Model):
    """An ad of this account."""

    type: str = "ad"
    ad_id: int = 0
    ad_title: str = ""
    ad_is_deleted: bool = False
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


AccountTransactionPeer = Union[
    AccountTransactionPeerExternal,
    AccountTransactionPeerMainAccount,
    AccountTransactionPeerRelatedAccount,
    AccountTransactionPeerAd,
    UnknownObject,
]

_ACCOUNT_PEERS: dict[str, Any] = {
    "external": AccountTransactionPeerExternal,
    "main_account": AccountTransactionPeerMainAccount,
    "related_account": AccountTransactionPeerRelatedAccount,
    "ad": AccountTransactionPeerAd,
}


def _account_peer(data: Any) -> Any:
    if not isinstance(data, dict):
        return None
    return _ACCOUNT_PEERS.get(data.get("type"), UnknownObject).from_dict(data)


@dataclass(frozen=True)
class AccountTransaction(_Model, _HasCurrency):
    """One movement of money in or out of an account budget."""

    peer: Optional[AccountTransactionPeer] = None
    date: int = 0
    currency: Optional[str] = None
    #: Negative for a withdrawal from the account budget.
    amount: float = 0.0
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    _nested = {"peer": _account_peer}

    @property
    def when(self) -> datetime | None:
        """:attr:`date` as an aware UTC ``datetime``."""
        return _dt(self.date)


@dataclass(frozen=True)
class AccountTransactionsList(_Model):
    """A page of account transactions."""

    total_count: int = 0
    transactions: List[AccountTransaction] = field(default_factory=list)
    #: Pass it back as ``offset`` for the next page; ``None`` on the last one.
    next_offset: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    _nested = {"transactions": _many(AccountTransaction.from_dict)}

    def __iter__(self) -> Iterator[AccountTransaction]:
        return iter(self.transactions)

    def __len__(self) -> int:
        return len(self.transactions)


@dataclass(frozen=True)
class AccountReportItem(_Model, _HasCurrency):
    """One ad's line in a monthly account report."""

    ad_id: int = 0
    ad_title: str = ""
    ad_is_deleted: bool = False
    views: int = 0
    #: Video opens.
    opens: int = 0
    clicks: int = 0
    #: User actions counted as conversions (formerly ``joins``).
    actions: int = 0
    currency: Optional[str] = None
    spent_budget: float = 0.0
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    _aliases = {"actions": ("joins",)}


# ---------------------------------------------------------------------- #
# Uploaded media
# ---------------------------------------------------------------------- #


@dataclass(frozen=True)
class AdPhoto(_Model):
    """A photo uploaded for display in an ad.  Ids are per-account."""

    photo_id: str = ""
    photo_url: str = ""
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class AdVideo(_Model):
    """A video uploaded for display in an ad.  Ids are per-account."""

    video_id: str = ""
    video_url: str = ""
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class WebsitePhoto(_Model):
    """A photo of the promoted website.  Ids are per-account."""

    photo_id: str = ""
    photo_url: str = ""
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


# ---------------------------------------------------------------------- #
# Targeting catalogue
# ---------------------------------------------------------------------- #


@dataclass(frozen=True)
class TargetLanguage(_Model):
    language_code: str = ""
    name: str = ""
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class TargetTopic(_Model):
    topic_id: int = 0
    name: str = ""
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class TargetCountry(_Model):
    country_code: str = ""
    name: str = ""
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class TargetLocation(_Model):
    """A city, populated area, district and so on."""

    location_id: int = 0
    name: str = ""
    country_code: Optional[str] = None
    region: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class TargetLocationList(_Model):
    """A page of location search results."""

    total_count: int = 0
    locations: List[TargetLocation] = field(default_factory=list)
    next_offset: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    _nested = {"locations": _many(TargetLocation.from_dict)}

    def __iter__(self) -> Iterator[TargetLocation]:
        return iter(self.locations)

    def __len__(self) -> int:
        return len(self.locations)


@dataclass(frozen=True)
class TargetChannel(_Model):
    """A channel, as resolved for targeting.

    ``channel_id`` may exceed 32 bits (Python ints are unbounded, so this only
    matters when you store it elsewhere: use a 64-bit column).
    """

    channel_id: int = 0
    title: Optional[str] = None
    username: Optional[str] = None
    #: JPEG or SVG.
    photo_url: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class TargetBot(_Model):
    """A bot, as resolved for targeting.  ``bot_id`` may exceed 32 bits."""

    bot_id: int = 0
    title: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


# ---------------------------------------------------------------------- #
# Audiences
# ---------------------------------------------------------------------- #


@dataclass(frozen=True)
class Audience(_Model):
    """A retargeting audience built from phone numbers."""

    audience_id: int = 0
    title: str = ""
    #: Approximate number of phone numbers.  ``0`` is empty; ``50`` means
    #: fewer than 100.
    size: int = 0
    ads_count: int = 0
    created_date: int = 0
    updated_date: int = 0
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def created_at(self) -> datetime | None:
        return _dt(self.created_date)

    @property
    def updated_at(self) -> datetime | None:
        return _dt(self.updated_date)


@dataclass(frozen=True)
class AudiencesList(_Model):
    total_count: int = 0
    audiences: List[Audience] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    _nested = {"audiences": _many(Audience.from_dict)}

    def __iter__(self) -> Iterator[Audience]:
        return iter(self.audiences)

    def __len__(self) -> int:
        return len(self.audiences)


# ---------------------------------------------------------------------- #
# Ad targets (as returned)
# ---------------------------------------------------------------------- #


@dataclass(frozen=True)
class AdTargetChannels(_Model):
    """Channel targeting, as returned on an :class:`Ad`."""

    type: str = "channels"
    languages: List[TargetLanguage] = field(default_factory=list)
    topics: List[TargetTopic] = field(default_factory=list)
    exclude_topics: List[TargetTopic] = field(default_factory=list)
    channels: List[TargetChannel] = field(default_factory=list)
    exclude_channels: List[TargetChannel] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    _nested = {
        "languages": _many(TargetLanguage.from_dict),
        "topics": _many(TargetTopic.from_dict),
        "exclude_topics": _many(TargetTopic.from_dict),
        "channels": _many(TargetChannel.from_dict),
        "exclude_channels": _many(TargetChannel.from_dict),
    }


@dataclass(frozen=True)
class AdTargetUsers(_Model):
    """User targeting, as returned on an :class:`Ad`."""

    type: str = "users"
    countries: List[TargetCountry] = field(default_factory=list)
    locations: List[TargetLocation] = field(default_factory=list)
    languages: List[TargetLanguage] = field(default_factory=list)
    topics: List[TargetTopic] = field(default_factory=list)
    intersect_topics: bool = False
    exclude_topics: List[TargetTopic] = field(default_factory=list)
    channels: List[TargetChannel] = field(default_factory=list)
    exclude_channels: List[TargetChannel] = field(default_factory=list)
    audiences: List[Audience] = field(default_factory=list)
    exclude_audiences: List[Audience] = field(default_factory=list)
    device: Optional[str] = None
    exclude_political_channels: bool = False
    political_channels_only: bool = False
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    _nested = {
        "countries": _many(TargetCountry.from_dict),
        "locations": _many(TargetLocation.from_dict),
        "languages": _many(TargetLanguage.from_dict),
        "topics": _many(TargetTopic.from_dict),
        "exclude_topics": _many(TargetTopic.from_dict),
        "channels": _many(TargetChannel.from_dict),
        "exclude_channels": _many(TargetChannel.from_dict),
        "audiences": _many(Audience.from_dict),
        "exclude_audiences": _many(Audience.from_dict),
    }


@dataclass(frozen=True)
class AdTargetBots(_Model):
    """Bot targeting, as returned on an :class:`Ad`."""

    type: str = "bots"
    bots: List[TargetBot] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    _nested = {"bots": _many(TargetBot.from_dict)}


@dataclass(frozen=True)
class AdTargetSearch(_Model):
    """Search-query targeting, as returned on an :class:`Ad`."""

    type: str = "search"
    search_queries: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


AdTarget = Union[AdTargetChannels, AdTargetUsers, AdTargetBots, AdTargetSearch, UnknownObject]

_TARGETS: dict[str, Any] = {
    "channels": AdTargetChannels,
    "users": AdTargetUsers,
    "bots": AdTargetBots,
    "search": AdTargetSearch,
}


def _target(data: Any) -> Any:
    if not isinstance(data, dict):
        return None
    return _TARGETS.get(data.get("type"), UnknownObject).from_dict(data)


# ---------------------------------------------------------------------- #
# Ads
# ---------------------------------------------------------------------- #


@dataclass(frozen=True)
class AdSchedule(_Model):
    """When an ad is shown, hour by hour, as returned on an :class:`Ad`."""

    #: Seven 24-bit masks, Monday first; bit ``n`` is the hour ``n:00–n+1:00``.
    week_hours_mask: List[int] = field(default_factory=list)
    #: Offset from UTC in seconds.
    timezone: Optional[int] = None
    use_viewer_timezone: bool = False
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    def hours(self, weekday: int) -> list[int]:
        """Hours (0–23) the ad runs on ``weekday`` (0 = Monday)."""
        masks = self.week_hours_mask
        if not 0 <= weekday < len(masks):
            return []
        return [hour for hour in range(24) if masks[weekday] >> hour & 1]

    @property
    def is_set(self) -> bool:
        """``False`` when every mask is zero, which means "any time"."""
        return any(self.week_hours_mask)


@dataclass(frozen=True)
class DeclineReason(_Model):
    """Why an ad was declined in review."""

    text: str = ""
    description_html: str = ""
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class Ad(_Model, _HasCurrency):
    """An advertisement.

    ``target`` is filled only when the call was made with
    ``return_target=True``.
    """

    ad_id: int = 0
    title: str = ""
    currency: Optional[str] = None
    text: str = ""
    photo: Optional[AdPhoto] = None
    video: Optional[AdVideo] = None
    promote_url: str = ""
    cpm: float = 0.0
    placement: Optional[str] = None
    target: Optional[AdTarget] = None
    impression_frequency: Optional[int] = None
    website_name: Optional[str] = None
    website_photo: Optional[WebsitePhoto] = None
    button: Optional[str] = None
    conversion_event_id: Optional[str] = None
    additional_info: Optional[str] = None
    show_userpic: bool = False
    spent_budget: float = 0.0
    remaining_budget: float = 0.0
    daily_spent_budget: Optional[float] = None
    daily_budget_limit: Optional[float] = None
    views: int = 0
    opens: Optional[int] = None
    clicks: Optional[int] = None
    #: Conversions of :attr:`action_type` (formerly ``joins``).
    actions: int = 0
    action_type: Optional[str] = None
    created_date: int = 0
    is_paused: bool = False
    activate_date: Optional[int] = None
    deactivate_date: Optional[int] = None
    schedule: Optional[AdSchedule] = None
    #: ``stopped``, ``ready_for_review``, ``in_review``, ``declined``,
    #: ``active`` or ``on_hold``.
    status: str = ""
    decline_reason: Optional[DeclineReason] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    _nested = {
        "photo": _one(AdPhoto.from_dict),
        "video": _one(AdVideo.from_dict),
        "target": _target,
        "website_photo": _one(WebsitePhoto.from_dict),
        "schedule": _one(AdSchedule.from_dict),
        "decline_reason": _one(DeclineReason.from_dict),
    }
    _aliases = {"actions": ("joins",)}

    @property
    def created_at(self) -> datetime | None:
        return _dt(self.created_date)

    @property
    def activate_at(self) -> datetime | None:
        return _dt(self.activate_date)

    @property
    def deactivate_at(self) -> datetime | None:
        return _dt(self.deactivate_date)

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def is_declined(self) -> bool:
        return self.status == "declined"

    @property
    def needs_review_submission(self) -> bool:
        """``True`` for ``ready_for_review``: call ``submit_ad_for_review``."""
        return self.status == "ready_for_review"

    @property
    def ctr(self) -> float | None:
        """Clicks per view, when the API reported clicks and there were views."""
        if self.clicks is None or not self.views:
            return None
        return self.clicks / self.views


@dataclass(frozen=True)
class AdList(_Model):
    """A page of ads."""

    total_count: int = 0
    ads: List[Ad] = field(default_factory=list)
    next_offset: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    _nested = {"ads": _many(Ad.from_dict)}

    def __iter__(self) -> Iterator[Ad]:
        return iter(self.ads)

    def __len__(self) -> int:
        return len(self.ads)


@dataclass(frozen=True)
class AdTransactionPeerAccount(_Model):
    """The account the ad belongs to — a budget top-up or withdrawal."""

    type: str = "account"
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class AdTransactionPeerViews(_Model):
    """Paid views — the ad's spend."""

    type: str = "views"
    views: int = 0
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


AdTransactionPeer = Union[AdTransactionPeerAccount, AdTransactionPeerViews, UnknownObject]

_AD_PEERS: dict[str, Any] = {"account": AdTransactionPeerAccount, "views": AdTransactionPeerViews}


def _ad_peer(data: Any) -> Any:
    if not isinstance(data, dict):
        return None
    return _AD_PEERS.get(data.get("type"), UnknownObject).from_dict(data)


@dataclass(frozen=True)
class AdTransaction(_Model, _HasCurrency):
    """One movement of money in or out of an ad budget."""

    peer: Optional[AdTransactionPeer] = None
    date: int = 0
    currency: Optional[str] = None
    #: Negative for a withdrawal from the ad budget.
    amount: float = 0.0
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    _nested = {"peer": _ad_peer}

    @property
    def when(self) -> datetime | None:
        """:attr:`date` as an aware UTC ``datetime``."""
        return _dt(self.date)


@dataclass(frozen=True)
class AdTransactionsList(_Model):
    total_count: int = 0
    transactions: List[AdTransaction] = field(default_factory=list)
    next_offset: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    _nested = {"transactions": _many(AdTransaction.from_dict)}

    def __iter__(self) -> Iterator[AdTransaction]:
        return iter(self.transactions)

    def __len__(self) -> int:
        return len(self.transactions)


@dataclass(frozen=True)
class AdStatItem(_Model, _HasCurrency):
    """Stats for one interval ``[from_time, to_time)``."""

    from_time: int = 0
    to_time: int = 0
    views: int = 0
    opens: int = 0
    clicks: int = 0
    actions: int = 0
    currency: Optional[str] = None
    spent_budget: float = 0.0
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    _aliases = {"actions": ("joins",)}

    @property
    def start(self) -> datetime | None:
        return _dt(self.from_time)

    @property
    def end(self) -> datetime | None:
        return _dt(self.to_time)


# ---------------------------------------------------------------------- #
# Pixel
# ---------------------------------------------------------------------- #


@dataclass(frozen=True)
class Pixel(_Model):
    """The account's Pixel Tag."""

    pixel_id: str = ""
    #: Place before ``</head>`` on every page of the site.
    code_snippet: str = ""
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class PixelEvent(_Model):
    """A conversion event tracked by the pixel."""

    event_id: str = ""
    title: str = ""
    type: str = ""
    #: ``"inactive"`` or ``"active"``.
    status: str = ""
    ads_count: int = 0
    created_date: int = 0
    #: ``None`` if never triggered, or not within the last 7 days.
    last_triggered_date: Optional[int] = None
    #: Created by the platform; cannot be edited or deleted.
    auto_created: bool = False
    #: Extra snippet for the element that triggers the event, when it needs one.
    code_snippet: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def created_at(self) -> datetime | None:
        return _dt(self.created_date)

    @property
    def last_triggered_at(self) -> datetime | None:
        return _dt(self.last_triggered_date)


@dataclass(frozen=True)
class PixelEventsList(_Model):
    total_count: int = 0
    events: List[PixelEvent] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    _nested = {"events": _many(PixelEvent.from_dict)}

    def __iter__(self) -> Iterator[PixelEvent]:
        return iter(self.events)

    def __len__(self) -> int:
        return len(self.events)
