"""A fake HTTP session, so the tests never touch the network."""

from __future__ import annotations

import json as jsonlib
from typing import Any

import pytest

from telead import Client


class FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        json_body: Any = None,
        *,
        text: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._json = json_body
        self.headers = headers or {}
        self.text = text if text is not None else (
            jsonlib.dumps(json_body) if json_body is not None else ""
        )

    def json(self) -> Any:
        if self._json is None:
            raise ValueError("no json body")
        return self._json


def ok(result: Any = True, **kwargs: Any) -> FakeResponse:
    """A successful API response carrying ``result``."""
    return FakeResponse(200, {"ok": True, "result": result}, **kwargs)


def fail(error: str, status: int = 200, **kwargs: Any) -> FakeResponse:
    """A failed API response with the ``error`` code."""
    return FakeResponse(status, {"ok": False, "error": error}, **kwargs)


class FakeSession:
    """Serves queued responses and records every request it was asked to make."""

    def __init__(self) -> None:
        self.responses: list[Any] = []
        self.requests: list[dict[str, Any]] = []
        self.closed = False

    def queue(self, *responses: Any) -> "FakeSession":
        self.responses.extend(responses)
        return self

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.requests.append({"method": method, "url": url, **kwargs})
        if not self.responses:
            return ok(True)
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response

    def close(self) -> None:
        self.closed = True

    # -- assertion helpers --------------------------------------------- #

    @property
    def last(self) -> dict[str, Any]:
        return self.requests[-1]

    @property
    def last_json(self) -> Any:
        return self.requests[-1].get("json")

    @property
    def last_method(self) -> str:
        return self.requests[-1]["url"].rsplit("/", 1)[-1]


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Record backoff sleeps instead of waiting."""
    slept: list[float] = []
    monkeypatch.setattr("telead.client.time.sleep", slept.append)
    return slept


@pytest.fixture
def session() -> FakeSession:
    return FakeSession()


@pytest.fixture
def client(session: FakeSession) -> Client:
    return Client("TOKEN", base_url="https://api.test", session=session)  # type: ignore[arg-type]


AD = {
    "ad_id": 42,
    "title": "Autumn launch",
    "currency": "TON",
    "text": "Hello",
    "promote_url": "https://t.me/example",
    "cpm": 2.5,
    "placement": "channel_post",
    "spent_budget": 1.25,
    "remaining_budget": 48.75,
    "views": 1000,
    "clicks": 25,
    "actions": 3,
    "created_date": 1726000000,
    "status": "active",
}
