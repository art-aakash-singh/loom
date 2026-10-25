"""The I/O half of context building: everything `build` needs, loaded and frozen."""

from datetime import UTC, datetime
from uuid import UUID

from loom_api.chat.records import MessageRecord
from loom_api.chat.repository import ChatRepository
from loom_api.context.types import ContextInput, GenerationSettings, PathMessage


def _to_path_message(message: MessageRecord) -> PathMessage:
    if message.token_count is None:
        # Only streaming rows lack a count, and a path ending at a user message has none.
        raise ValueError(f"message {message.id} has no token_count (status {message.status})")
    return PathMessage(
        id=message.id,
        role=message.role,
        content=tuple(message.content),
        status=message.status,
        token_count=message.token_count,
    )


async def gather(
    repo: ChatRepository,
    user_message_id: UUID,
    *,
    system_prompt: str,
    settings: GenerationSettings,
) -> ContextInput:
    """Load the path root → `user_message_id` and read the clock, once, for `build`."""
    path = await repo.path_to(user_message_id)
    if not path or path[-1].id != user_message_id or path[-1].role != "user":
        raise ValueError(f"{user_message_id} is not a user message")
    return ContextInput(
        path=tuple(_to_path_message(m) for m in path),
        system_prompt=system_prompt,
        now=datetime.now(UTC),
        settings=settings,
    )
