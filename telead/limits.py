"""Platform constants: the endpoint, currencies, enumerations and caps.

Every value here comes from the Telegram Ads API documentation
(https://ads.telegram.org/docs/api, as of September 18, 2026).
"""

from __future__ import annotations

__all__ = [
    "DEFAULT_BASE_URL",
    "CURRENCIES",
    "Currency",
    "PLACEMENTS",
    "BUTTONS",
    "AD_STATUSES",
    "ACTION_TYPES",
    "PIXEL_EVENT_TYPES",
    "PIXEL_EVENT_STATUSES",
    "TRANSACTION_STATUSES",
    "DEVICES",
    "TARGET_TYPES",
    "STAT_INTERVALS",
    "STAT_MAX_POINTS",
    "SCHEDULE_TIMEZONES",
    "SCHEDULE_MASK_MAX",
    "IDEMPOTENCY_KEY_MAX",
    "IDEMPOTENT_METHODS",
    "AD_TEXT_MAX",
    "AD_TITLE_MAX_BYTES",
    "PROMOTE_URL_MAX",
    "WEBSITE_NAME_MAX",
    "ADDITIONAL_INFO_MAX",
    "IMPRESSION_FREQUENCY_RANGE",
    "SCHEDULE_DAYS_AHEAD_MAX",
    "ADS_LIST_LIMIT_MAX",
    "LIST_LIMIT_DEFAULT",
    "AUDIENCE_TITLE_MAX",
    "AUDIENCE_PHONES_PER_CALL",
    "AUDIENCE_PHONES_MAX",
    "PIXEL_EVENT_TITLE_MAX",
    "ACCOUNT_FIELD_LIMITS",
    "REPORT_YEAR_RANGE",
    "TARGET_LIMITS",
    "UPLOAD_LIMITS",
    "UploadLimit",
]

DEFAULT_BASE_URL = "https://promoteapi.telegram.org"

# ---------------------------------------------------------------------- #
# Currencies
# ---------------------------------------------------------------------- #


class Currency:
    """One of the currencies an account can be denominated in.

    Attributes:
        code: ``"EUR"``, ``"TON"`` or ``"XTR"``.
        name: Human-readable name.
        cpm_precision: Decimal places kept for CPMs and budgets.
        amount_precision: Decimal places kept for transferred amounts.
    """

    __slots__ = ("code", "name", "cpm_precision", "amount_precision")

    def __init__(self, code: str, name: str, cpm_precision: int, amount_precision: int) -> None:
        self.code = code
        self.name = name
        self.cpm_precision = cpm_precision
        self.amount_precision = amount_precision

    def round_cpm(self, value: float) -> float:
        """Round a CPM or budget the way the API will."""
        return round(float(value), self.cpm_precision)

    def round_amount(self, value: float) -> float:
        """Round a transferred amount the way the API will."""
        return round(float(value), self.amount_precision)

    def __repr__(self) -> str:
        return f"Currency({self.code!r})"


#: Currency code -> precision rules.  The currency is fixed when an account
#: is created; every monetary field is in the account's currency.
CURRENCIES = {
    "EUR": Currency("EUR", "Euros", 2, 5),
    "TON": Currency("TON", "Grams", 2, 5),
    "XTR": Currency("XTR", "Telegram Stars", 0, 3),
}

# ---------------------------------------------------------------------- #
# Enumerations
# ---------------------------------------------------------------------- #

#: Where an ad is shown.  Pass it explicitly to ``createAd``; the API still
#: infers it from ``target.type`` when omitted, but says that may change.
PLACEMENTS = ("channel_post", "bot_banner", "search_result", "video_banner")

#: Button labels for an ad promoting an external link.  Empty means
#: "Open Website".
BUTTONS = (
    "subscribe", "view", "read", "learn_more", "download", "open",
    "sign_up", "buy", "order", "play", "try", "leave_request",
)

#: ``Ad.status`` values.
AD_STATUSES = ("stopped", "ready_for_review", "in_review", "declined", "active", "on_hold")

#: Event types a pixel event can be created with.
PIXEL_EVENT_TYPES = (
    "page_view", "add_to_cart", "add_to_wishlist", "customize_product",
    "initiate_checkout", "add_payment_info", "purchase", "contact", "lead",
    "schedule", "complete_registration", "submit_application", "start_trial",
    "subscribe", "view_content", "search", "find_location", "donate", "custom",
)

#: ``Ad.action_type`` values: the platform-tracked actions plus every pixel
#: event type (``landing_view`` appears on returned events and ads only).
ACTION_TYPES = (
    "join", "start_bot", "launch_miniapp", "send_message", "page_view", "landing_view",
) + PIXEL_EVENT_TYPES[1:]

PIXEL_EVENT_STATUSES = ("inactive", "active")

#: ``TransactionStatus.status`` values.
TRANSACTION_STATUSES = ("in_progress", "failed", "completed")

#: ``InputAdTargetUsers.device`` values.
DEVICES = ("ios", "android", "mobile", "desktop")

#: ``InputAdTarget.type`` values.
TARGET_TYPES = ("channels", "users", "bots", "search")

#: Accepted ``interval`` values for stats, in seconds: 5 minutes or 1 day.
STAT_INTERVALS = (300, 86400)
#: A stats period may span at most this many intervals.
STAT_MAX_POINTS = 1000

#: Offsets from UTC, in seconds, accepted by ``InputAdSchedule.timezone``.
SCHEDULE_TIMEZONES = (
    -43200, -39600, -36000, -34200, -32400, -28800, -25200, -21600, -18000,
    -14400, -12600, -10800, -9000, -7200, -3600, 0, 3600, 7200, 10800, 12600,
    14400, 16200, 18000, 19800, 20700, 21600, 23400, 25200, 28800, 31500,
    32400, 34200, 36000, 37800, 39600, 43200, 45900, 46800, 49500, 50400,
)
#: 24 bits, one per hour of the day.
SCHEDULE_MASK_MAX = (1 << 24) - 1

# ---------------------------------------------------------------------- #
# Idempotency
# ---------------------------------------------------------------------- #

IDEMPOTENCY_KEY_MAX = 128

#: Methods documented with an ``idempotency_key`` parameter.  The client
#: gives each call to these a key of its own, so retrying them is safe.
IDEMPOTENT_METHODS = frozenset({
    "createAccount",
    "increaseAccountBudget",
    "decreaseAccountBudget",
    "createAd",
    "increaseAdBudget",
    "decreaseAdBudget",
    "createAudience",
    "createPixel",
    "createPixelEvent",
})

# ---------------------------------------------------------------------- #
# Field caps
# ---------------------------------------------------------------------- #

AD_TEXT_MAX = 160            # characters — what the audience sees
AD_TITLE_MAX_BYTES = 128     # UTF-8 bytes — only shown in the Ads interface
PROMOTE_URL_MAX = 256
WEBSITE_NAME_MAX = 40
ADDITIONAL_INFO_MAX = 64
IMPRESSION_FREQUENCY_RANGE = (1, 4)
#: ``activate_date`` / ``deactivate_date`` may be at most this far ahead.
SCHEDULE_DAYS_AHEAD_MAX = 365

ADS_LIST_LIMIT_MAX = 100
LIST_LIMIT_DEFAULT = 100

AUDIENCE_TITLE_MAX = 64
#: Phone numbers accepted by one ``createAudience`` / ``editAudience`` call.
AUDIENCE_PHONES_PER_CALL = 10_000
#: Phone numbers one retargeting audience may hold.
AUDIENCE_PHONES_MAX = 1_000_000

PIXEL_EVENT_TITLE_MAX = 64

#: ``createAccount`` / ``editAccountInfo`` field -> (min, max) characters.
ACCOUNT_FIELD_LIMITS = {
    "title": (1, 128),
    "full_name": (1, 256),
    "email": (1, 64),
    "country": (1, 128),
    "city": (1, 128),
    "legal_name": (0, 256),
}

REPORT_YEAR_RANGE = (2021, 2100)

#: Targeting caps.  "Combined" caps count included and excluded items together.
TARGET_LIMITS = {
    "language_codes": 8,
    "country_codes": 8,
    "location_ids": 20,
    "topics_combined": 20,
    "channels_combined": 100,
    "bot_ids": 100,
    "audience_ids": 4,
    "exclude_audience_ids": 4,
    "audiences_combined": 10,
    "search_queries": 10,
}

# ---------------------------------------------------------------------- #
# Uploads
# ---------------------------------------------------------------------- #

MB = 1024 * 1024


class UploadLimit:
    """What an upload method accepts."""

    __slots__ = ("max_bytes", "mime_types", "extensions", "requirements")

    def __init__(self, max_bytes: int, mime_types: tuple[str, ...],
                 extensions: tuple[str, ...], requirements: str) -> None:
        self.max_bytes = max_bytes
        self.mime_types = mime_types
        self.extensions = extensions
        self.requirements = requirements

    def __repr__(self) -> str:
        return f"UploadLimit(max_bytes={self.max_bytes}, mime_types={self.mime_types})"


#: Upload method -> limits.  Pixel dimensions, aspect ratio and duration are
#: checked by the API only; the library checks size and format.
UPLOAD_LIMITS = {
    "uploadAdPhoto": UploadLimit(
        5 * MB, ("image/jpeg", "image/png"), (".jpg", ".jpeg", ".png"),
        "JPEG or PNG, up to 5 MB, at least 640 px wide, 16:9",
    ),
    "uploadAdVideo": UploadLimit(
        20 * MB, ("video/mp4",), (".mp4",),
        "MP4, up to 20 MB, at least 640 px wide, 16:9, 3–60 seconds",
    ),
    "uploadWebsitePhoto": UploadLimit(
        1 * MB, ("image/jpeg", "image/png"), (".jpg", ".jpeg", ".png"),
        "JPEG or PNG, up to 1 MB, at least 150 × 150 px",
    ),
}
