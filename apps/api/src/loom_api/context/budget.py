"""Token budgeting. Pure: no DB, no clock (ruff TID251 enforces the imports)."""

import math

from loom_api.context.types import ContextTooLarge, GenerationSettings, PathMessage

# chars/4 under-counts code and non-Latin text; pad estimated counts so a budget that "fits"
# on paper still fits the provider's real tokenizer.
ESTIMATE_PADDING = 1.25
# Role markers and turn framing the provider adds around each message.
PER_MESSAGE_OVERHEAD = 4


def message_cost(message: PathMessage) -> int:
    """Tokens this message is budgeted at once it is sent as input."""
    # A finished reply's count is the provider's own output_tokens; everything else is chars/4.
    exact = message.role == "assistant" and message.status == "complete"
    count = message.token_count if exact else math.ceil(message.token_count * ESTIMATE_PADDING)
    return count + PER_MESSAGE_OVERHEAD


def _turns(path: tuple[PathMessage, ...]) -> list[tuple[PathMessage, ...]]:
    """Split the path into turns: a user message plus the replies that follow it."""
    turns: list[list[PathMessage]] = []
    for message in path:
        if message.role == "user" or not turns:
            turns.append([message])
        else:
            turns[-1].append(message)
    return [tuple(t) for t in turns]


def _cost(turn: tuple[PathMessage, ...]) -> int:
    return sum(message_cost(m) for m in turn)


def fit_to_budget(
    path: tuple[PathMessage, ...], system_tokens: int, settings: GenerationSettings
) -> tuple[PathMessage, ...]:
    """Return the part of `path` that fits next to the system prompt and the reserved reply.

    Drops whole turns, never a user message without its reply. Priority, highest first:
    the last turn (the message being answered; ContextTooLarge if even that cannot fit),
    then the first turn (it usually states the task, and keeping it keeps the cached prefix
    stable), then as many of the most recent turns as fit, contiguously.

    # TODO(human)
    # Context: once a conversation goes over budget, this function keeps shrinking the
    # window by exactly one turn as the conversation grows — see
    # test_kept_window_is_stable_as_the_conversation_grows (apps/api/tests/context/test_budget.py).
    # The cut point moves on every single request, so almost nothing past the first turn
    # survives between requests, and the provider's prompt cache never gets a hit on long
    # conversations — the whole point of keeping the first turn stable is defeated the moment
    # the middle shifts too.
    # Task: when the window has to shrink, cut down to roughly 70% of the budget in one go
    # (not just enough to fit), and keep that same cut point on later turns until the
    # conversation outgrows it again — so the kept window only moves in steps, not every turn.
    # Weigh: `build` must stay pure (no DB, no clock), so fit_to_budget can't remember where
    # it cut last time on its own. Two ways to get a cut point that repeats:
    #   (a) store the last cut point (e.g. the kept turn count, or the oldest kept message id)
    #       on the conversation, and pass it in as an argument — most accurate, but it's state
    #       that gather() has to load and something has to write back after each build.
    #   (b) make the cut point a pure function of path length alone, e.g. only ever cut back to
    #       a turn count that's a multiple of N — no stored state, but the 70%-of-budget target
    #       becomes approximate, and it can still shift by one turn right at a multiple-of-N
    #       boundary.
    # Remove the xfail marker on the test once this lands.
    """
    budget = (
        settings.context_window
        - settings.max_output_tokens
        - math.ceil(system_tokens * ESTIMATE_PADDING)
    )
    turns = _turns(path)
    if not turns:
        return path
    if sum(_cost(t) for t in turns) <= budget:
        return path

    last = turns[-1]
    remaining = budget - _cost(last)
    if remaining < 0:
        raise ContextTooLarge(
            f"the latest message alone needs ~{_cost(last)} tokens; "
            f"{budget} are left after the system prompt and the reply"
        )

    head: tuple[PathMessage, ...] = ()
    middle = turns[1:-1]
    if len(turns) > 1 and _cost(turns[0]) <= remaining:
        head = turns[0]
        remaining -= _cost(turns[0])
    elif len(turns) > 1:
        # The first turn does not fit: it competes with the rest like any other old turn.
        middle = turns[:-1]

    tail: list[tuple[PathMessage, ...]] = []
    for turn in reversed(middle):
        if _cost(turn) > remaining:
            break  # stay contiguous: a gap the model cannot see is worse than less history
        tail.insert(0, turn)
        remaining -= _cost(turn)

    return head + tuple(m for turn in tail for m in turn) + last
