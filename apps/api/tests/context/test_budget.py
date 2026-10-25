from uuid import uuid4

import pytest
from loom_api.chat.records import MessageStatus
from loom_api.context.budget import fit_to_budget, message_cost
from loom_api.context.types import ContextTooLarge, GenerationSettings, PathMessage
from loom_api.llm.types import Role


def msg(role: Role, tokens: int, status: MessageStatus = "complete") -> PathMessage:
    return PathMessage(id=uuid4(), role=role, content=(), status=status, token_count=tokens)


def settings(window: int, output: int = 100) -> GenerationSettings:
    return GenerationSettings(model="fake", max_output_tokens=output, context_window=window)


def turn(user_tokens: int, reply_tokens: int) -> tuple[PathMessage, PathMessage]:
    return msg("user", user_tokens), msg("assistant", reply_tokens)


def test_returns_the_path_unchanged_when_it_fits() -> None:
    path = (*turn(10, 20), msg("user", 10))
    assert fit_to_budget(path, system_tokens=10, settings=settings(1_000)) == path


def test_estimated_counts_are_padded_and_finished_replies_are_not() -> None:
    assert message_cost(msg("assistant", 100)) == 104
    assert message_cost(msg("user", 100)) == 129
    assert message_cost(msg("assistant", 100, status="cancelled")) == 129


def test_keeps_the_first_turn_and_the_most_recent_turns_dropping_the_middle() -> None:
    first, middle, recent = turn(100, 100), turn(100, 100), turn(100, 100)
    last = msg("user", 100)
    path = (*first, *middle, *recent, last)
    # Each turn costs 129 + 104 = 233; the last message 129. Room for the last + two turns.
    kept = fit_to_budget(path, system_tokens=0, settings=settings(100 + 129 + 2 * 233))
    assert kept == (*first, *recent, last)


def test_never_keeps_a_reply_without_its_user_message() -> None:
    path = (*turn(100, 100), *turn(100, 100), msg("user", 100))
    kept = fit_to_budget(path, system_tokens=0, settings=settings(100 + 129 + 233 + 50))
    assert kept[0].role == "user"
    assert len(kept) == 3


def test_drops_an_oversized_first_turn_and_keeps_recent_history() -> None:
    first, recent, last = turn(5_000, 100), turn(100, 100), msg("user", 100)
    kept = fit_to_budget((*first, *recent, last), system_tokens=0, settings=settings(1_000))
    assert kept == (*recent, last)


def test_stops_at_the_first_turn_that_does_not_fit_instead_of_skipping_over_it() -> None:
    older, big, last = turn(10, 10), turn(2_000, 10), msg("user", 10)
    kept = fit_to_budget(
        (*turn(10, 10), *older, *big, last), system_tokens=0, settings=settings(1_000)
    )
    assert big[0] not in kept
    assert older[0] not in kept


def test_raises_when_the_message_being_answered_cannot_fit() -> None:
    with pytest.raises(ContextTooLarge):
        fit_to_budget((msg("user", 1_000),), system_tokens=0, settings=settings(1_000))


def test_the_system_prompt_counts_against_the_budget() -> None:
    path = (*turn(100, 100), msg("user", 100))
    kept = fit_to_budget(path, system_tokens=200, settings=settings(100 + 129 + 233 + 100))
    assert kept == (path[-1],)


@pytest.mark.xfail(
    strict=True,
    reason="fit_to_budget has no memory of where it last cut, so the window slides by one "
    "turn on every request once over budget. See the TODO(human) on fit_to_budget in "
    "budget.py. Remove this marker once the fix lands.",
)
def test_kept_window_is_stable_as_the_conversation_grows() -> None:
    """A cut point that moves every turn means almost nothing in the kept history survives
    from one request to the next, so the provider's prompt cache never gets a hit on long
    conversations. Once over budget, the window should only move when it has to — not on
    every single new turn.
    """
    first = turn(100, 100)
    last = msg("user", 100)
    # Room for the first turn, exactly two middle turns, and the last message.
    window = settings(100 + 129 + 2 * 233 + 129)

    def kept_window(num_middle_turns: int) -> tuple[PathMessage, ...]:
        middle = tuple(m for _ in range(num_middle_turns) for m in turn(100, 100))
        kept = fit_to_budget((*first, *middle, last), system_tokens=0, settings=window)
        return kept[len(first) : -1]  # drop the head and the last message; what remains

    # Three turns over budget in a row: the window should move at most once, not three times.
    windows = [kept_window(n) for n in (3, 4, 5)]
    assert len({w[0].id for w in windows}) < len(windows)
