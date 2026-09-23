"""Objects you send: ad targets and schedules.

Each one serializes with :meth:`to_dict` and checks itself against the
documented caps with :meth:`validate`.  Anywhere the client takes one of
these, a plain ``dict`` in the API's own shape works too.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, List, Mapping, Optional, Sequence, Union

from .errors import ValidationError
from .limits import DEVICES, SCHEDULE_MASK_MAX, SCHEDULE_TIMEZONES, TARGET_LIMITS

__all__ = [
    "InputAdTarget",
    "InputAdTargetChannels",
    "InputAdTargetUsers",
    "InputAdTargetBots",
    "InputAdTargetSearch",
    "InputAdSchedule",
    "PeerRef",
    "WEEKDAYS",
]

#: A channel or bot: ``"@username"`` (recommended) or a numeric id this
#: account has already resolved by username.
PeerRef = Union[int, str]

#: Day names accepted by :meth:`InputAdSchedule.weekly`, Monday first.
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _compact(data: dict[str, Any]) -> dict[str, Any]:
    """Drop unset values, so only what the caller chose is sent."""
    return {k: v for k, v in data.items() if v is not None and v != [] and v is not False}


def _check_count(name: str, values: Sequence[Any], maximum: int) -> None:
    if len(values) > maximum:
        raise ValidationError(f"{name} has {len(values)} items; the limit is {maximum}.")


def _check_combined(name: str, first: Sequence[Any], second: Sequence[Any], maximum: int) -> None:
    total = len(first) + len(second)
    if total > maximum:
        raise ValidationError(
            f"{name}: {total} included and excluded together; the limit is {maximum}."
        )


def _check_peers(name: str, values: Sequence[Any]) -> None:
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            raise ValidationError(f"{name} entries must be '@username' or an int, got {value!r}.")
        if isinstance(value, str) and not value.startswith("@") and not value.lstrip("-").isdigit():
            raise ValidationError(
                f"{name} entry {value!r} should be '@username' or a numeric id."
            )


@dataclass
class InputAdTargetChannels:
    """Show the ad in channels — by language, by topics, or by specific channels.

    Three mutually exclusive ways in:

    * ``language_codes`` alone (up to 8),
    * ``topic_ids`` in exactly one language (up to 20 topics),
    * ``channel_ids`` (up to 100), with no languages or topics.

    Topics and channels can also be excluded.  Included plus excluded topics
    may not exceed 20, and channels 100.
    """

    language_codes: List[str] = field(default_factory=list)
    topic_ids: List[int] = field(default_factory=list)
    exclude_topic_ids: List[int] = field(default_factory=list)
    channel_ids: List[PeerRef] = field(default_factory=list)
    exclude_channel_ids: List[PeerRef] = field(default_factory=list)

    type = "channels"

    def validate(self) -> None:
        _check_count("language_codes", self.language_codes, TARGET_LIMITS["language_codes"])
        _check_combined("topics", self.topic_ids, self.exclude_topic_ids,
                        TARGET_LIMITS["topics_combined"])
        _check_combined("channels", self.channel_ids, self.exclude_channel_ids,
                        TARGET_LIMITS["channels_combined"])
        _check_peers("channel_ids", self.channel_ids)
        _check_peers("exclude_channel_ids", self.exclude_channel_ids)
        if self.channel_ids and (self.topic_ids or self.language_codes):
            raise ValidationError(
                "channel_ids cannot be combined with topic_ids or language_codes."
            )
        if self.topic_ids and len(self.language_codes) != 1:
            raise ValidationError("topic_ids needs exactly one entry in language_codes.")

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, **_compact({
            "language_codes": list(self.language_codes),
            "topic_ids": list(self.topic_ids),
            "exclude_topic_ids": list(self.exclude_topic_ids),
            "channel_ids": list(self.channel_ids),
            "exclude_channel_ids": list(self.exclude_channel_ids),
        })}


@dataclass
class InputAdTargetUsers:
    """Show the ad to users — by country, location, language, interests,
    channel audiences, retargeting audiences and device.

    ``country_codes`` must have exactly one entry when ``location_ids`` is
    used, and every location must be in that country.
    """

    country_codes: List[str] = field(default_factory=list)
    location_ids: List[int] = field(default_factory=list)
    language_codes: List[str] = field(default_factory=list)
    topic_ids: List[int] = field(default_factory=list)
    #: Require every topic, not any one of them.
    intersect_topics: bool = False
    exclude_topic_ids: List[int] = field(default_factory=list)
    channel_ids: List[PeerRef] = field(default_factory=list)
    exclude_channel_ids: List[PeerRef] = field(default_factory=list)
    audience_ids: List[int] = field(default_factory=list)
    exclude_audience_ids: List[int] = field(default_factory=list)
    #: ``"ios"``, ``"android"``, ``"mobile"`` or ``"desktop"``.
    device: Optional[str] = None
    exclude_political_channels: bool = False
    political_channels_only: bool = False

    type = "users"

    def validate(self) -> None:
        _check_count("country_codes", self.country_codes, TARGET_LIMITS["country_codes"])
        _check_count("location_ids", self.location_ids, TARGET_LIMITS["location_ids"])
        _check_count("language_codes", self.language_codes, TARGET_LIMITS["language_codes"])
        _check_combined("topics", self.topic_ids, self.exclude_topic_ids,
                        TARGET_LIMITS["topics_combined"])
        _check_combined("channels", self.channel_ids, self.exclude_channel_ids,
                        TARGET_LIMITS["channels_combined"])
        _check_count("audience_ids", self.audience_ids, TARGET_LIMITS["audience_ids"])
        _check_count("exclude_audience_ids", self.exclude_audience_ids,
                     TARGET_LIMITS["exclude_audience_ids"])
        _check_combined("audiences", self.audience_ids, self.exclude_audience_ids,
                        TARGET_LIMITS["audiences_combined"])
        _check_peers("channel_ids", self.channel_ids)
        _check_peers("exclude_channel_ids", self.exclude_channel_ids)
        if self.location_ids and len(self.country_codes) != 1:
            raise ValidationError("location_ids needs exactly one entry in country_codes.")
        if self.device is not None and self.device not in DEVICES:
            raise ValidationError(f"device must be one of {', '.join(DEVICES)}; got {self.device!r}.")
        if self.exclude_political_channels and self.political_channels_only:
            raise ValidationError(
                "exclude_political_channels and political_channels_only contradict each other."
            )

    def to_dict(self) -> dict[str, Any]:
        # country_codes is not marked Optional in the docs, so it is always sent.
        return {"type": self.type, "country_codes": list(self.country_codes), **_compact({
            "location_ids": list(self.location_ids),
            "language_codes": list(self.language_codes),
            "topic_ids": list(self.topic_ids),
            "intersect_topics": self.intersect_topics,
            "exclude_topic_ids": list(self.exclude_topic_ids),
            "channel_ids": list(self.channel_ids),
            "exclude_channel_ids": list(self.exclude_channel_ids),
            "audience_ids": list(self.audience_ids),
            "exclude_audience_ids": list(self.exclude_audience_ids),
            "device": self.device,
            "exclude_political_channels": self.exclude_political_channels,
            "political_channels_only": self.political_channels_only,
        })}


@dataclass
class InputAdTargetBots:
    """Show the ad in specific bots (up to 100)."""

    bot_ids: List[PeerRef] = field(default_factory=list)

    type = "bots"

    def validate(self) -> None:
        _check_count("bot_ids", self.bot_ids, TARGET_LIMITS["bot_ids"])
        _check_peers("bot_ids", self.bot_ids)

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, **_compact({"bot_ids": list(self.bot_ids)})}


@dataclass
class InputAdTargetSearch:
    """Show the ad in search results for up to 10 keywords or phrases."""

    search_queries: List[str] = field(default_factory=list)

    type = "search"

    def validate(self) -> None:
        _check_count("search_queries", self.search_queries, TARGET_LIMITS["search_queries"])
        for query in self.search_queries:
            if not isinstance(query, str) or not query.strip():
                raise ValidationError(f"search_queries entries must be non-empty strings, got {query!r}.")

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "search_queries": list(self.search_queries)}


InputAdTarget = Union[
    InputAdTargetChannels, InputAdTargetUsers, InputAdTargetBots, InputAdTargetSearch,
]


def _hours_mask(hours: Iterable[int]) -> int:
    mask = 0
    for hour in hours:
        if isinstance(hour, bool) or not isinstance(hour, int) or not 0 <= hour <= 23:
            raise ValidationError(f"Hours must be integers 0–23, got {hour!r}.")
        mask |= 1 << hour
    return mask


@dataclass
class InputAdSchedule:
    """When to show an ad, hour by hour, across a week.

    Build it from hours rather than bitmasks::

        InputAdSchedule.every_day(range(9, 18), timezone=3 * 3600)
        InputAdSchedule.weekly({"mon": range(9, 18), "sat": [10, 11, 12]}, timezone=0)
        InputAdSchedule.every_day(range(18, 23), use_viewer_timezone=True)  # users targeting only

    To remove an ad's schedule, pass ``schedule=False`` to ``edit_ad``.
    """

    #: Seven 24-bit masks, Monday first; bit ``n`` is the hour ``n:00–n+1:00``.
    week_hours_mask: List[int] = field(default_factory=lambda: [0] * 7)
    #: Offset from UTC in seconds; one of :data:`~telead.limits.SCHEDULE_TIMEZONES`.
    #: Required unless ``use_viewer_timezone`` is set.
    timezone: Optional[int] = None
    #: Apply the schedule in each viewer's own timezone (users targeting only).
    use_viewer_timezone: bool = False

    @classmethod
    def every_day(cls, hours: Iterable[int], *, timezone: Optional[int] = None,
                  use_viewer_timezone: bool = False) -> "InputAdSchedule":
        """The same hours on all seven days."""
        mask = _hours_mask(hours)
        return cls([mask] * 7, timezone=timezone, use_viewer_timezone=use_viewer_timezone)

    @classmethod
    def weekly(cls, days: Mapping[Union[int, str], Iterable[int]], *,
               timezone: Optional[int] = None,
               use_viewer_timezone: bool = False) -> "InputAdSchedule":
        """Hours per day.  Keys are ``0``–``6`` (Monday first) or ``"mon"``…``"sun"``;
        days left out show nothing."""
        masks = [0] * 7
        for day, hours in days.items():
            if isinstance(day, str):
                key = day.strip().lower()[:3]
                if key not in WEEKDAYS:
                    raise ValidationError(f"Unknown weekday {day!r}; use one of {', '.join(WEEKDAYS)}.")
                index = WEEKDAYS.index(key)
            elif isinstance(day, int) and not isinstance(day, bool) and 0 <= day <= 6:
                index = day
            else:
                raise ValidationError(f"Weekday must be 0–6 or a day name, got {day!r}.")
            masks[index] |= _hours_mask(hours)
        return cls(masks, timezone=timezone, use_viewer_timezone=use_viewer_timezone)

    def hours(self, weekday: int) -> list[int]:
        """Hours (0–23) the schedule covers on ``weekday`` (0 = Monday)."""
        return [hour for hour in range(24) if self.week_hours_mask[weekday] >> hour & 1]

    def validate(self) -> None:
        masks = self.week_hours_mask
        if len(masks) != 7:
            raise ValidationError(f"week_hours_mask needs exactly 7 numbers, got {len(masks)}.")
        for mask in masks:
            if isinstance(mask, bool) or not isinstance(mask, int) or not 0 <= mask <= SCHEDULE_MASK_MAX:
                raise ValidationError(
                    f"Each week_hours_mask value must be an int 0–{SCHEDULE_MASK_MAX}, got {mask!r}."
                )
        if self.timezone is not None and self.timezone not in SCHEDULE_TIMEZONES:
            raise ValidationError(
                f"timezone {self.timezone} is not an accepted UTC offset; "
                "see telead.limits.SCHEDULE_TIMEZONES."
            )
        if self.timezone is None and not self.use_viewer_timezone and any(masks):
            raise ValidationError("A schedule needs timezone=, or use_viewer_timezone=True.")

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"week_hours_mask": list(self.week_hours_mask)}
        if self.timezone is not None:
            data["timezone"] = self.timezone
        if self.use_viewer_timezone:
            data["use_viewer_timezone"] = True
        return data


def serialize(value: Any) -> Any:
    """``to_dict()`` an input object; pass anything else through."""
    to_dict = getattr(value, "to_dict", None)
    return to_dict() if callable(to_dict) else value


def validate_input(value: Any) -> None:
    """Run an input object's own checks, if it has any."""
    check = getattr(value, "validate", None)
    if callable(check):
        check()
