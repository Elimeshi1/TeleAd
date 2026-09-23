from __future__ import annotations

import pytest

from telead.errors import (
    APIError,
    AuthenticationError,
    IdempotencyMismatchError,
    InvalidRequestError,
    NotEnoughBudgetError,
    PermissionDeniedError,
    RateLimitError,
    RequestInProgressError,
    ServerError,
    UnknownPeerError,
    error_from_response,
)


@pytest.mark.parametrize("code, cls", [
    ("ACCESS_TOKEN_REQUIRED", AuthenticationError),
    ("ACCESS_TOKEN_INVALID", AuthenticationError),
    ("ACCESS_TOKEN_EXPIRED", AuthenticationError),
    ("CHANNEL_ID_UNKNOWN", UnknownPeerError),
    ("BOT_ID_UNKNOWN", UnknownPeerError),
    ("NOT_ENOUGH_BUDGET", NotEnoughBudgetError),
    ("IDEMPOTENT_PARAM_MISMATCH", IdempotencyMismatchError),
    ("IDEMPOTENT_REQUEST_IN_PROGRESS", RequestInProgressError),
    ("AD_TITLE_REQUIRED", InvalidRequestError),
    ("CPM_INVALID", InvalidRequestError),
    ("TEXT_TOO_LONG", InvalidRequestError),
    ("MAIN_ACCOUNT_REQUIRED", PermissionDeniedError),
    ("RETARGETING_DISABLED", PermissionDeniedError),
    ("ACCESS_DENIED", PermissionDeniedError),
    ("PIXEL_DISABLED", PermissionDeniedError),
    ("SOMETHING_NEW", APIError),
])
def test_code_mapping(code, cls):
    error = error_from_response(200, {"ok": False, "error": code}, method="createAd")
    assert type(error) is cls
    assert error.code == code
    assert error.method == "createAd"


def test_unknown_peer_is_an_invalid_request():
    assert issubclass(UnknownPeerError, InvalidRequestError)


def test_flood_wait_carries_seconds():
    error = error_from_response(200, {"ok": False, "error": "FLOOD_WAIT_12"})
    assert isinstance(error, RateLimitError)
    assert error.retry_after == 12.0 and error.retryable


def test_http_429_reads_retry_after():
    error = error_from_response(429, "", {"Retry-After": "4"})
    assert isinstance(error, RateLimitError) and error.retry_after == 4.0


@pytest.mark.parametrize("status, body", [(502, "<html>Bad gateway</html>"), (200, ""), (500, None)])
def test_non_envelope_is_server_error(status, body):
    error = error_from_response(status, body)
    assert isinstance(error, ServerError) and error.retryable
    assert error.code == f"HTTP_{status}"


def test_unexpected_4xx_without_envelope():
    error = error_from_response(404, "Not Found")
    assert type(error) is APIError
    assert "Not Found" in str(error)


def test_str_includes_method_and_status():
    error = error_from_response(200, {"ok": False, "error": "AD_ID_INVALID"}, method="editAd")
    assert str(error) == "AD_ID_INVALID [method=editAd, http=200]"


def test_retryable_flags():
    assert not InvalidRequestError("X").retryable
    assert RequestInProgressError("X").retryable


def test_permission_errors_are_not_invalid_requests():
    # MAIN_ACCOUNT_REQUIRED ends in _REQUIRED but is about the account, not a parameter.
    error = error_from_response(200, {"ok": False, "error": "MAIN_ACCOUNT_REQUIRED"})
    assert not isinstance(error, InvalidRequestError) and not error.retryable
