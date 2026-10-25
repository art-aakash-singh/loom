"""The pure half of context building. No DB, no clock, no randomness (ruff TID251 enforces
the imports): same ContextInput in, same ProviderRequest out."""

from datetime import UTC

from loom_api.context.budget import fit_to_budget
from loom_api.context.types import ContextInput, PathMessage, ProviderRequest
from loom_api.llm.estimate import estimate_tokens_by_chars
from loom_api.llm.types import Message


def _system(inp: ContextInput) -> str:
    # Date, not time: the system prompt is the front of the cached prefix, so it may change
    # at most once a day. A timestamp would make every request a cache miss.
    return f"{inp.system_prompt}\n\nToday's date is {inp.now.astimezone(UTC).date().isoformat()}."


def _text(message: PathMessage) -> str:
    return "".join(block["text"] for block in message.content)


def _to_messages(path: tuple[PathMessage, ...]) -> tuple[Message, ...]:
    """Provider messages: alternating, starting with the user.

    A reply contributes whatever text it has, finished or not: a cancelled or failed reply
    with partial text is what the user saw, so the model sees it too. A reply with no text
    contributes nothing, which leaves two user messages adjacent; they are merged, because
    the provider wants strict alternation and the user did say both.
    """
    messages: list[Message] = []
    for m in path:
        text = _text(m)
        if not text:
            continue
        if messages and messages[-1].role == m.role:
            messages[-1] = Message(m.role, f"{messages[-1].content}\n\n{text}")
        else:
            messages.append(Message(m.role, text))
    # Budgeting can only drop whole turns from a user-first path, so this holds; check anyway,
    # because a provider rejecting the request is a worse place to find out.
    if not messages or messages[0].role != "user" or messages[-1].role != "user":
        raise ValueError("context must start and end with a user message")
    return tuple(messages)


def build(inp: ContextInput) -> ProviderRequest:
    """Turn the gathered path into the request the provider streams from.

    Raises ContextTooLarge (from fit_to_budget) when even the message being answered does
    not fit the model's context window.
    """
    system = _system(inp)
    kept = fit_to_budget(inp.path, estimate_tokens_by_chars(system), inp.settings)
    return ProviderRequest(system=system, messages=_to_messages(kept), settings=inp.settings)
