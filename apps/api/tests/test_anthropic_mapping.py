import logging

import pytest
from loom_api.llm.anthropic import _map_status, _map_stop_reason
from loom_api.llm.types import ErrorKind, StopReason


@pytest.mark.parametrize(
    ("status", "kind"),
    [
        (429, "rate_limited"),
        (529, "overloaded"),
        (401, "auth_failed"),
        (403, "auth_failed"),
        (400, "invalid_request"),
        (422, "invalid_request"),
        (500, "unexpected"),
        (404, "unexpected"),
    ],
)
def test_status_mapping(status: int, kind: ErrorKind) -> None:
    assert _map_status(status) == kind


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("end_turn", "complete"),
        ("stop_sequence", "complete"),
        ("max_tokens", "max_tokens"),
        ("refusal", "refusal"),
    ],
)
def test_known_stop_reasons(raw: str, expected: StopReason) -> None:
    assert _map_stop_reason(raw) == expected


def test_unknown_stop_reason_is_complete_and_warns(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="loom_api.llm.anthropic"):
        assert _map_stop_reason("pause_turn") == "complete"

    assert "pause_turn" in caplog.text
