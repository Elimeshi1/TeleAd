"""telead — a Python library for the Telegram Ads API.

One method per endpoint of ``https://promoteapi.telegram.org``, with typed
responses, local validation, idempotency keys, retries and pagination::

    from telead import Client, InputAdTargetChannels

    with Client("<ACCESS_TOKEN>") as client:
        ad = client.create_ad(
            title="Autumn launch",
            text="Everything you need to know, in one channel.",
            promote_url="https://t.me/mychannel",
            cpm=2.5,
            placement="channel_post",
            target=InputAdTargetChannels(channel_ids=["@somechannel"]),
            initial_budget=50,
        )
        print(ad.ad_id, ad.status)

Implements the Telegram Ads API as documented on September 18, 2026.
"""

from __future__ import annotations

__version__ = "0.1.0"

from .client import Client
from .errors import (
    APIError,
    AuthenticationError,
    IdempotencyMismatchError,
    InvalidRequestError,
    NotEnoughBudgetError,
    PermissionDeniedError,
    RateLimitError,
    RequestInProgressError,
    ServerError,
    TeleadError,
    TransportError,
    UnknownPeerError,
    ValidationError,
)
from .inputs import (
    InputAdSchedule,
    InputAdTarget,
    InputAdTargetBots,
    InputAdTargetChannels,
    InputAdTargetSearch,
    InputAdTargetUsers,
)
from .limits import CURRENCIES, DEFAULT_BASE_URL
from .models import (
    Account,
    AccountInfo,
    AccountReportItem,
    AccountTransaction,
    AccountTransactionsList,
    Ad,
    AdList,
    AdPhoto,
    AdSchedule,
    AdStatItem,
    AdTarget,
    AdTargetBots,
    AdTargetChannels,
    AdTargetSearch,
    AdTargetUsers,
    AdTransaction,
    AdTransactionsList,
    AdVideo,
    Audience,
    AudiencesList,
    DeclineReason,
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

__all__ = [
    "__version__",
    # client
    "Client",
    # inputs
    "InputAdTarget",
    "InputAdTargetChannels",
    "InputAdTargetUsers",
    "InputAdTargetBots",
    "InputAdTargetSearch",
    "InputAdSchedule",
    # models
    "Account",
    "AccountInfo",
    "AccountReportItem",
    "AccountTransaction",
    "AccountTransactionsList",
    "Ad",
    "AdList",
    "AdPhoto",
    "AdSchedule",
    "AdStatItem",
    "AdTarget",
    "AdTargetBots",
    "AdTargetChannels",
    "AdTargetSearch",
    "AdTargetUsers",
    "AdTransaction",
    "AdTransactionsList",
    "AdVideo",
    "Audience",
    "AudiencesList",
    "DeclineReason",
    "Pixel",
    "PixelEvent",
    "PixelEventsList",
    "RelatedAccountsList",
    "TargetBot",
    "TargetChannel",
    "TargetCountry",
    "TargetLanguage",
    "TargetLocation",
    "TargetLocationList",
    "TargetTopic",
    "TransactionStatus",
    "WebsitePhoto",
    # errors
    "TeleadError",
    "ValidationError",
    "TransportError",
    "APIError",
    "AuthenticationError",
    "InvalidRequestError",
    "UnknownPeerError",
    "NotEnoughBudgetError",
    "PermissionDeniedError",
    "IdempotencyMismatchError",
    "RequestInProgressError",
    "RateLimitError",
    "ServerError",
    # constants
    "CURRENCIES",
    "DEFAULT_BASE_URL",
]
