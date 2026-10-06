from types import SimpleNamespace
import json
import pytest
from server import ai, db, config
from server.models import Observations


class FakeClient:
    def __init__(self, response=None, error=None):
        self.models = self
        self.response = response
        self.error = error
        self.calls = 0

    def generate_content(self, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return SimpleNamespace(
            text=self.response,
            usage_metadata=SimpleNamespace(
                prompt_token_count=100,
                candidates_token_count=50,
                thoughts_token_count=0,
            ),
        )

    def close(self):
        pass


def test_provider_response_is_validated_and_cached(client, monkeypatch):
    provider = FakeClient(
        json.dumps(
            {
                "moments": [
                    {
                        "start_seconds": 0,
                        "end_seconds": 2,
                        "description": "Dribbling practice",
                        "uncertainty": "",
                    }
                ]
            }
        )
    )
    monkeypatch.setattr(ai, "client", lambda: provider)
    first = ai.complete(None, "describe", Observations)
    second = ai.complete(None, "describe", Observations)
    assert first == second and provider.calls == 1
    assert len(db.rows("SELECT * FROM usage")) == 1
    assert db.rows("SELECT * FROM usage")[0]["status"] == "settled"


def test_malformed_response_not_cached_but_charge_recorded(client, monkeypatch):
    provider = FakeClient("not valid JSON")
    monkeypatch.setattr(ai, "client", lambda: provider)
    with pytest.raises(ValueError):
        ai.complete(None, "bad response", Observations)
    assert not db.rows("SELECT * FROM cache")
    assert db.spend() > 0


@pytest.mark.parametrize(
    "error", [TimeoutError("timeout"), RuntimeError("429 simulated rate limit")]
)
def test_failed_cloud_call_keeps_reservation_and_no_retry(client, monkeypatch, error):
    provider = FakeClient(error=error)
    monkeypatch.setattr(ai, "client", lambda: provider)
    with pytest.raises(type(error)):
        ai.complete(None, "timeout", Observations)
    assert provider.calls == 1
    assert db.rows("SELECT * FROM usage")[0]["status"] == "unconfirmed"
    assert db.spend() > 0


def test_budget_blocks_before_cloud_call(client, monkeypatch):
    monkeypatch.setattr(config, "SPEND_LIMIT", 0)
    provider = FakeClient("{}")
    monkeypatch.setattr(ai, "client", lambda: provider)
    with pytest.raises(ValueError):
        ai.complete(None, "describe", Observations)
    assert provider.calls == 0
