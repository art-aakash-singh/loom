from collections.abc import Sequence

from loom_api.chat.records import MessageRecord
from loom_api.llm.types import Message


def build_context(chain: Sequence[MessageRecord]) -> list[Message]:
    """Turn the root→leaf chain into provider messages.

    M2a policy: include everything except assistant messages with no content (a reply that
    failed or was cancelled before its first token). No token budgeting or truncation yet.
    """
    return [
        Message(m.role, "".join(block["text"] for block in m.content))
        for m in chain
        if not (m.role == "assistant" and not m.content)
    ]
