"""Exceptions raised by :mod:`telead`.

Every Telegram Ads API response is a JSON object with a boolean ``ok``.  A
failure looks like::

    {"ok": false, "error": "AD_TITLE_REQUIRED"}

``error`` is a string code, and the HTTP status is ``200`` for ordinary
failures, so the code is what identifies them.  :func:`error_from_response`
maps it onto the classes below.
"""

from __future__ import annotations

import re
from typing import Any

__all__ = [
    "TeleadError",
    "ValidationError",
    "TransportError",
    "APIError",
    "AuthenticationError",
    "InvalidRequestError",
    "UnknownPeerError",
    "NotEnoughBudgetError",
    "IdempotencyMismatchError",
    "RequestInProgressError",
    "RateLimitError",
    "ServerError",
    "error_from_response",
]


class TeleadError(Exception):
    """Base class for everything this library raises."""


class ValidationError(TeleadError, ValueError):
    """A request was rejected locally, before it reached the API."""


class TransportError(TeleadError):
    """The request never produced an HTTP response (network failure, timeout)."""


class APIError(TeleadError):
    """An error response from the API.

    Attributes:
        code: The ``error`` string, for example ``"AD_TITLE_REQUIRED"``.
            Branch on this.
        method: The API method that failed, for example ``"createAd"``.
        status: The HTTP status — ``200`` for ordinary API errors.
        raw: The full response body.
    """

    #: ``True`` when the same request may reasonably be sent again after a backoff.
    retryable = False

    def __init__(
        self,
        code: str,
        *,
        method: str | None = None,
        status: int | None = None,
        raw: Any = None,
        description: str | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.method = method
        self.status = status
        self.description = description
        self.raw = raw if raw is not None else {}

    def __str__(self) -> str:
        text = self.code
        if self.description and self.description != self.code:
            text = f"{text}: {self.description}"
        where = ", ".join(
            f"{k}={v}" for k, v in (("method", self.method), ("http", self.status)) if v is not None
        )
        return f"{text} [{where}]" if where else text


class AuthenticationError(APIError):
    """``ACCESS_TOKEN_REQUIRED`` / ``ACCESS_TOKEN_INVALID`` — no token, or a revoked one."""


class InvalidRequestError(APIError):
    """A parameter is missing, malformed or out of range (``*_REQUIRED``, ``*_INVALID`` …)."""


class UnknownPeerError(InvalidRequestError):
    """``CHANNEL_ID_UNKNOWN`` / ``BOT_ID_UNKNOWN``.

    A numeric channel or bot id can only be used after this account has
    resolved it by username.  Pass ``"@username"`` instead, or resolve it
    once with :meth:`~telead.Client.get_target_channel` /
    :meth:`~telead.Client.get_target_bot`.
    """


class NotEnoughBudgetError(APIError):
    """``NOT_ENOUGH_BUDGET`` — the source budget cannot cover the amount."""


class IdempotencyMismatchError(APIError):
    """``IDEMPOTENT_PARAM_MISMATCH`` — a key was reused with different parameters."""


class RequestInProgressError(APIError):
    """``IDEMPOTENT_REQUEST_IN_PROGRESS`` — the first request with this key is still running.

    Safe to repeat after a short wait: the repeat replays the first result.
    """

    retryable = True


class RateLimitError(APIError):
    """Too many requests — HTTP 429, or a ``FLOOD_WAIT_<seconds>`` style code.

    The Ads API documentation does not describe rate limits; this class
    exists so that one, if returned, is backed off rather than surfaced.
    """

    retryable = True

    def __init__(self, *args: Any, retry_after: float | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        #: Seconds to wait, from ``Retry-After`` or the error code, when known.
        self.retry_after = retry_after


class ServerError(APIError):
    """HTTP 5xx, or a response that was not the documented JSON envelope."""

    retryable = True


#: ``error`` code -> exception class.
_CODE_MAP: dict[str, type[APIError]] = {
    "ACCESS_TOKEN_REQUIRED": AuthenticationError,
    "ACCESS_TOKEN_INVALID": AuthenticationError,
    "CHANNEL_ID_UNKNOWN": UnknownPeerError,
    "BOT_ID_UNKNOWN": UnknownPeerError,
    "NOT_ENOUGH_BUDGET": NotEnoughBudgetError,
    "IDEMPOTENT_PARAM_MISMATCH": IdempotencyMismatchError,
    "IDEMPOTENT_REQUEST_IN_PROGRESS": RequestInProgressError,
    "TOO_MANY_REQUESTS": RateLimitError,
}

#: Code suffixes that mean the request itself was at fault.
_INVALID_SUFFIXES = ("_REQUIRED", "_INVALID", "_TOO_LONG", "_TOO_SHORT", "_EMPTY", "_TOO_MANY")

_FLOOD_RE = re.compile(r"^FLOOD_WAIT_(\d+)$")


def error_from_response(
    status: int,
    body: Any,
    headers: Any = None,
    *,
    method: str | None = None,
) -> APIError:
    """Build the right :class:`APIError` from an HTTP status and a parsed body."""
    code = None
    description = None
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, str) and error:
            code = error
        elif isinstance(error, dict):  # defensive: a structured error
            code = str(error.get("code") or error.get("error") or "") or None
            description = error.get("message") or error.get("description")
        description = description or body.get("description")

    kwargs: dict[str, Any] = dict(method=method, status=status, raw=body, description=description)

    if code is None:
        # Not the documented envelope: a gateway page, an empty body, a 5xx.
        fallback = f"HTTP_{status}"
        if isinstance(body, str) and body.strip():
            kwargs["description"] = body.strip()[:200]
        if status == 429:
            return RateLimitError(fallback, retry_after=_retry_after(headers), **kwargs)
        if status >= 500 or status == 200:
            return ServerError(fallback, **kwargs)
        return APIError(fallback, **kwargs)

    flood = _FLOOD_RE.match(code)
    if flood or status == 429:
        retry_after = float(flood.group(1)) if flood else _retry_after(headers)
        return RateLimitError(code, retry_after=retry_after, **kwargs)

    cls = _CODE_MAP.get(code)
    if cls is None:
        if code.startswith("ACCESS_TOKEN_"):
            cls = AuthenticationError
        elif code.endswith(_INVALID_SUFFIXES):
            cls = InvalidRequestError
        elif status >= 500:
            cls = ServerError
        else:
            cls = APIError
    return cls(code, **kwargs)


def _retry_after(headers: Any) -> float | None:
    if not headers:
        return None
    try:
        value = headers.get("Retry-After")
    except AttributeError:
        return None
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None
