"""The experimental time model cannot turn bad timestamps into Storyroom cuts."""

import json
from math import inf, nan
from types import SimpleNamespace

import pytest

from server import ai, config, db
from server.localization import candidate_context, localized_frames


def test_context_and_frame_conversion_are_bounded(clip):
    candidate = candidate_context("c1", clip, "hash", 60, 90, 180)
    assert (candidate.context_start, candidate.context_end) == (0, 165)
    assert localized_frames(candidate, 1.1, 3.1) == (33, 93)
    edge = candidate_context("c2", clip, "hash", 0, 30, 40)
    assert (edge.context_start, edge.context_end) == (0, 40)
    assert localized_frames(edge, 0, 40 / 30) == (0, 40)
    with pytest.raises(ValueError, match="Invalid verified"):
        candidate_context("c3", clip, "hash", 30, 30, 40)


@pytest.mark.parametrize("start,end", [
    (-0.1, 2), (2, 2), (2, 5.6), (nan, 2), (0, inf),
])
def test_invalid_or_different_event_times_are_rejected(clip, start, end):
    candidate = candidate_context("c1", clip, "hash", 60, 90, 180)
    with pytest.raises(ValueError):
        localized_frames(candidate, start, end)


def test_nearby_missed_onset_allowed_but_distant_repeat_rejected(clip):
    candidate = candidate_context("c1", clip, "hash", 60, 90, 180)
    # The action begins after the old cut, but remains in the bounded context.
    assert localized_frames(candidate, 4.0, 4.7) == (120, 141)
    distant = candidate_context("c2", clip, "hash", 100, 130, 220)
    with pytest.raises(ValueError, match="too far"):
        localized_frames(distant, 0, 0.3)


class FakeClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []
        self.models = self

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(
            text=json.dumps(self.response),
            usage_metadata=SimpleNamespace(
                prompt_token_count=300, candidates_token_count=30,
                thoughts_token_count=0,
            ),
        )

    def close(self):
        pass


def _result(decision="match", start=1.8, end=3.8, evidence="Visible action"):
    return {"results": [{
        "candidate_id": "c1", "decision": decision,
        "visible_evidence": evidence,
        "start_seconds": start, "end_seconds": end,
    }]}


def _setup(monkeypatch, fake):
    monkeypatch.setattr(config, "VISUAL_TIER", "unpaid")
    monkeypatch.setattr(ai, "embedding_client", lambda: fake)
    monkeypatch.setattr(ai, "verification_clip", lambda *_: b"video-content")


def test_valid_localization_uses_one_extra_request_and_its_own_cache(client, clip, monkeypatch):
    fake = FakeClient(_result())
    _setup(monkeypatch, fake)
    spec = [("c1", clip, "proxy-hash", 60, 90, 180)]
    ordinary_key = ai.visual_verifier_cache_key("skateboard trick", "proxy-hash", 60, 90)
    db.cache_set(ordinary_key, {
        "decision": "match", "visible_evidence": "Board leaves ground",
    })
    first, error = ai.localize_visual_matches("skateboard trick", spec)
    second, cached_error = ai.localize_visual_matches("skateboard trick", spec)
    assert error is None and cached_error is None
    assert first == second == {"c1": {
        "decision": "match", "visible_evidence": "Visible action",
        "start_frame": 54, "end_frame": 114,
    }}
    assert len(fake.calls) == 1
    assert len(fake.calls[0]["contents"]) == 3
    assert "verified anchor 2.000-3.000" in fake.calls[0]["contents"][0]
    assert db.cache_get(ordinary_key)["decision"] == "match"
    assert db.rows("SELECT status FROM usage") == [{"status": "settled"}]


@pytest.mark.parametrize("response", [
    _result(start=5.1, end=5.4),
    _result(start=1.8, end=5.6),
    _result(start=1.8, end=1.8),
    _result(evidence=""),
    _result(start=True),
    _result(start="1.0"),
    {"results": [{**_result()["results"][0], "candidate_id": "unknown"}]},
])
def test_invalid_model_ranges_do_not_escape_or_enter_cache(
    client, clip, monkeypatch, response,
):
    fake = FakeClient(response)
    _setup(monkeypatch, fake)
    spec = [("c1", clip, "proxy-hash", 60, 90, 180)]
    result, error = ai.localize_visual_matches("skateboard trick", spec)
    assert result == {}
    assert isinstance(error, ai.VisualProviderError)
    key = ai.visual_localization_cache_key(
        "skateboard trick", candidate_context(*spec[0])
    )
    assert db.cache_get(key) is None


@pytest.mark.parametrize("decision", ["uncertain", "no_match"])
def test_uncertain_or_absent_action_is_not_a_localized_positive(
    client, clip, monkeypatch, decision,
):
    fake = FakeClient(_result(decision=decision, start=0, end=0, evidence=""))
    _setup(monkeypatch, fake)
    result, error = ai.localize_visual_matches(
        "skateboard trick", [("c1", clip, "hash", 60, 90, 180)]
    )
    assert error is None
    assert result["c1"] == {"decision": decision, "visible_evidence": ""}


def test_provider_failure_or_paid_configuration_never_yields_new_cut(
    client, clip, monkeypatch,
):
    fake = FakeClient(error=RuntimeError("provider unavailable"))
    _setup(monkeypatch, fake)
    spec = [("c1", clip, "hash", 60, 90, 180)]
    result, error = ai.localize_visual_matches("skateboard trick", spec)
    assert result == {} and isinstance(error, ai.VisualProviderError)
    monkeypatch.setattr(config, "VISUAL_TIER", "paid")
    result, error = ai.localize_visual_matches("skateboard trick", spec)
    assert result == {} and "unpaid" in str(error)
    assert len(fake.calls) == 1


def test_damaged_localization_cache_cannot_return_out_of_bounds_frames(
    client, clip, monkeypatch,
):
    fake = FakeClient(_result())
    _setup(monkeypatch, fake)
    spec = ("c1", clip, "hash", 60, 90, 180)
    key = ai.visual_localization_cache_key(
        "skateboard trick", candidate_context(*spec)
    )
    db.cache_set(key, {
        "decision": "match", "visible_evidence": "board jumps",
        "start_frame": 60, "end_frame": 999,
    })
    result, error = ai.localize_visual_matches("skateboard trick", [spec])
    assert result == {} and "outside" in str(error)
    assert fake.calls == []
