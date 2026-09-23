# Testing

Code that manages ads moves real money, so it is worth testing without touching the API.

## A fake session

`Client` accepts any object with a `request()` method as its session, so a stand-in is a few lines:

```python
import json

class FakeResponse:
    def __init__(self, body, status_code=200, headers=None):
        self._body = body
        self.status_code = status_code
        self.headers = headers or {}
        self.text = json.dumps(body)

    def json(self):
        return self._body

def ok(result=True):
    return FakeResponse({"ok": True, "result": result})

def fail(code):
    return FakeResponse({"ok": False, "error": code})

class FakeSession:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def request(self, method, url, **kwargs):
        self.requests.append({"url": url, **kwargs})
        return self.responses.pop(0) if self.responses else ok()

    def close(self):
        pass
```

Every call is a `POST` to `<base_url>/<method>`; the parameters are in `kwargs["json"]` (or `kwargs["data"]` and `kwargs["files"]` for uploads), and the idempotency key, when there is one, is in `kwargs["headers"]["Idempotency-Key"]`.

## Asserting what your code sends

```python
from telead import Client

def pause_overspent(client):
    for ad in client.iter_ads():
        if ad.daily_budget_limit and ad.daily_spent_budget >= ad.daily_budget_limit:
            client.pause_ad(ad.ad_id)

def test_pauses_only_overspent_ads():
    session = FakeSession(
        ok({"total_count": 2, "ads": [
            {"ad_id": 1, "daily_budget_limit": 10, "daily_spent_budget": 10},
            {"ad_id": 2, "daily_budget_limit": 10, "daily_spent_budget": 3},
        ]}),
        ok({"ad_id": 1, "is_paused": True}),
    )
    client = Client("test-token", session=session)

    pause_overspent(client)

    assert [r["url"].rsplit("/", 1)[1] for r in session.requests] == ["getAdsList", "editAd"]
    assert session.requests[1]["json"] == {"ad_id": 1, "is_paused": True}
```

## Testing error paths

Queue a failure the same way:

```python
import pytest
from telead import Client, NotEnoughBudgetError

def test_top_up_stops_when_main_account_is_empty():
    session = FakeSession(fail("NOT_ENOUGH_BUDGET"))
    client = Client("test-token", session=session)
    with pytest.raises(NotEnoughBudgetError):
        client.increase_account_budget("rel-1", 100)
```

## Keeping retries out of the way

Retries sleep between attempts. Turn them off in tests, or patch the sleep:

```python
client = Client("test-token", session=session, max_retries=0)
```

```python
@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr("telead.client.time.sleep", lambda seconds: None)
```

## Building models directly

Every model has `from_dict`, taking the API's JSON:

```python
from telead import Ad

ad = Ad.from_dict({"ad_id": 1, "status": "declined",
                   "decline_reason": {"text": "Misleading", "description_html": "…"}})
assert ad.is_declined
```

## The library's own tests

```bash
git clone https://github.com/Elimeshi1/TeleAd.git
cd TeleAd
pip install -e ".[dev]"
pytest
```

They use the same technique — see [`tests/conftest.py`](https://github.com/Elimeshi1/TeleAd/blob/main/tests/conftest.py).
