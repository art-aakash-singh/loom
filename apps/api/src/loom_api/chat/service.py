import logging
from collections import defaultdict
from collections.abc import AsyncGenerator, Awaitable, Callable, Mapping
from contextlib import aclosing
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

import anyio

from loom_api.chat.errors import (
    ConversationNotFound,
    GenerationInProgress,
    InvalidGenerationTarget,
    InvalidParent,
    MessageNotFound,
)
from loom_api.chat.lock import GenerationLock
from loom_api.chat.records import (
    ContentBlock,
    ConversationRecord,
    FinalStatus,
    MessageRecord,
    MessageRef,
)
from loom_api.chat.repository import ChatRepository, LockedConversation
from loom_api.chat.schemas import (
    ChatEvent,
    ErrorEvent,
    MessageEndEvent,
    TextDeltaEvent,
    TurnStartedEvent,
    UsageOut,
)
from loom_api.chat.tree import ChildRef, resolve_leaf
from loom_api.context.build import build
from loom_api.context.gather import gather
from loom_api.context.types import ContextTooLarge, GenerationSettings
from loom_api.llm.base import LLMProvider
from loom_api.llm.types import (
    RETRYABLE,
    ErrorKind,
    MessageEnd,
    StopReason,
    StreamError,
    TextDelta,
    Usage,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = "You are Loom, a concise and helpful assistant."

CONTEXT_TOO_LARGE_MESSAGE = (
    "This conversation is too long for the model's context window. "
    "Start a new conversation, or edit an earlier message to branch off from there."
)

# Budget for each cleanup step that runs after cancellation (DB write, lock release).
_CLEANUP_TIMEOUT_S = 5

# Default parent for a new user message: wherever the conversation currently ends.
CurrentLeaf = Literal["current_leaf"]


async def _shielded(what: str, operation: Awaitable[object]) -> None:
    """Run cleanup that must survive cancellation; log failures instead of raising.

    Starlette cancels a disconnected stream through an anyio cancel scope, which re-delivers
    cancellation at every await until the scope exits. Without the shield, the first await in
    a `finally` block would be cancelled again and the write would never happen.
    The try/except sits outside the scopes because fail_after raises TimeoutError on exit.
    """
    try:
        with anyio.CancelScope(shield=True), anyio.fail_after(_CLEANUP_TIMEOUT_S):
            await operation
    except Exception:
        logger.exception("Cleanup step failed: %s", what)


def _text_content(parts: list[str]) -> list[ContentBlock]:
    return [{"type": "text", "text": "".join(parts)}] if parts else []


def _children_by_parent(refs: list[MessageRef]) -> dict[UUID, list[ChildRef]]:
    """Parent id → its children, oldest first. Roots have no parent, so no entry."""
    children: dict[UUID, list[ChildRef]] = defaultdict(list)
    for ref in refs:  # already ordered by created_at, id
        if ref.parent_id is not None:
            children[ref.parent_id].append(ChildRef(id=ref.id, created_at=ref.created_at))
    return dict(children)


def _sibling_ids(refs: list[MessageRef]) -> dict[UUID, list[UUID]]:
    """Message id → ids of every message sharing its parent (itself included), oldest first.

    Roots of one conversation count as siblings of each other (editing the first message).
    """
    groups: dict[UUID | None, list[UUID]] = defaultdict(list)
    for ref in refs:
        groups[ref.parent_id].append(ref.id)
    return {ref.id: groups[ref.parent_id] for ref in refs}


@dataclass(frozen=True)
class ConversationView:
    conversation: ConversationRecord
    path: list[MessageRecord]  # root → current leaf
    sibling_ids: Mapping[UUID, list[UUID]]


class Generation:
    """One assistant reply, ready to stream. Owns the generation lock until `events()` ends.

    If `events()` is never started (client vanished before the response began) the lock is
    only released by its TTL and the reply stays 'streaming' until the next startup sweep.
    """

    def __init__(
        self,
        *,
        repo: ChatRepository,
        lock: GenerationLock,
        provider: LLMProvider,
        settings: GenerationSettings,
        conversation_id: UUID,
        user_message: MessageRecord,
        assistant_message: MessageRecord,
        lock_token: str,
    ) -> None:
        self._repo = repo
        self._lock = lock
        self._provider = provider
        self._settings = settings
        self._conversation_id = conversation_id
        self._lock_token = lock_token
        self.user_message = user_message
        self.assistant_message = assistant_message

    async def events(self) -> AsyncGenerator[ChatEvent]:
        parts: list[str] = []
        # Stays "cancelled" if we leave through CancelledError or GeneratorExit: neither is
        # caught below, so they propagate untouched and `finally` records what we have.
        status: FinalStatus = "cancelled"
        stop_reason: StopReason | None = None
        error_kind: ErrorKind | None = None
        usage: Usage | None = None

        try:
            yield TurnStartedEvent(
                user_message_id=self.user_message.id,
                assistant_message_id=self.assistant_message.id,
            )
            try:
                context = await gather(
                    self._repo,
                    self.user_message.id,
                    system_prompt=SYSTEM_PROMPT,
                    settings=self._settings,
                )
                request = build(context)
                stream = self._provider.stream(request.system, request.messages, request.settings)
                async with aclosing(stream):
                    async for event in stream:
                        match event:
                            case TextDelta(text=text):
                                parts.append(text)
                                yield TextDeltaEvent(text=text)
                            case MessageEnd(stop_reason=reason, usage=usage):
                                status, stop_reason = "complete", reason
                                yield MessageEndEvent(
                                    stop_reason=reason,
                                    usage=UsageOut(
                                        input_tokens=usage.input_tokens,
                                        output_tokens=usage.output_tokens,
                                    ),
                                )
                            case StreamError(kind=kind, message=msg):
                                status, error_kind = "error", kind
                                yield ErrorEvent(
                                    kind=kind, message=msg, retryable=kind in RETRYABLE
                                )
                if status == "cancelled":
                    # The stream ended without MessageEnd or StreamError: a provider bug.
                    raise RuntimeError("provider stream ended without a terminal event")
            except ContextTooLarge as exc:
                logger.info("Context too large for %s: %s", self._settings.model, exc)
                status, error_kind = "error", "invalid_request"
                yield ErrorEvent(
                    kind="invalid_request", message=CONTEXT_TOO_LARGE_MESSAGE, retryable=False
                )
            except Exception:
                logger.exception("Generation failed unexpectedly")
                status, error_kind = "error", "unexpected"
                yield ErrorEvent(
                    kind="unexpected", message="Unexpected error while generating", retryable=False
                )
        finally:
            text = "".join(parts)
            await _shielded(
                "finalize assistant message",
                self._repo.finalize_assistant(
                    self.assistant_message.id,
                    status=status,
                    content=_text_content(parts),
                    stop_reason=stop_reason,
                    error_kind=error_kind,
                    usage=usage,
                    # The provider's own count when it finished; otherwise estimate what we got.
                    token_count=usage.output_tokens
                    if usage
                    else self._provider.estimate_tokens(text),
                ),
            )
            await _shielded(
                "release generation lock",
                self._lock.release(self._conversation_id, self._lock_token),
            )


class ChatService:
    def __init__(
        self,
        repo: ChatRepository,
        lock: GenerationLock,
        provider: LLMProvider,
        settings: GenerationSettings,
    ) -> None:
        self._repo = repo
        self._lock = lock
        self._provider = provider
        self._settings = settings

    async def create_conversation(self, title: str | None = None) -> ConversationRecord:
        return await self._repo.create_conversation(title)

    async def list_conversations(self, limit: int) -> list[ConversationRecord]:
        return await self._repo.list_conversations(limit)

    async def get_conversation(self, conversation_id: UUID) -> ConversationView:
        """The conversation, its active path (root → current leaf), and each step's siblings."""
        conversation = await self._repo.get_conversation(conversation_id)
        if conversation is None:
            raise ConversationNotFound(str(conversation_id))
        if conversation.current_leaf_id is None:
            return ConversationView(conversation, [], {})
        path = await self._repo.path_to(conversation.current_leaf_id)
        # Read after the path, so every message on it is in here (later ones are harmless).
        refs = await self._repo.message_refs(conversation_id)
        return ConversationView(conversation, path, _sibling_ids(refs))

    async def sweep_interrupted_generations(self) -> int:
        """Close replies left 'streaming' by a process that died. Run once at startup.

        Assumes a single API process: with several, this would also close replies that
        another live process is still streaming.
        """
        swept = await self._repo.fail_streaming_messages()
        if swept:
            logger.warning("Startup sweep: marked %d interrupted replies as error", swept)
        else:
            logger.info("Startup sweep: no interrupted replies")
        return swept

    async def send_message(
        self,
        conversation_id: UUID,
        text: str,
        parent_id: UUID | None | CurrentLeaf = "current_leaf",
    ) -> Generation:
        """Store a user message and an empty reply, and prepare it. Stream with `.events()`.

        `parent_id` defaults to the current leaf (a normal send). An edit passes the edited
        message's parent: an assistant message, or None for the first message.
        """
        token_count = self._provider.estimate_tokens(text)

        async def start(conv: LockedConversation) -> tuple[MessageRecord, MessageRecord]:
            if parent_id == "current_leaf":
                parent = conv.current_leaf_id
            else:
                parent = parent_id
                if parent is not None:
                    target = await conv.get_message(parent)
                    if target is None or target.role != "assistant":
                        raise InvalidParent(f"{parent} is not an assistant message here")
            user = await conv.add_user_message(
                parent_id=parent, text_=text, token_count=token_count
            )
            reply = await conv.add_streaming_reply(parent_id=user.id, model=self._settings.model)
            conv.set_leaf(reply.id)
            return user, reply

        return await self._start_generation(conversation_id, start)

    async def regenerate(self, conversation_id: UUID, user_message_id: UUID) -> Generation:
        """Answer an existing user message again, as a new sibling of its earlier replies."""

        async def start(conv: LockedConversation) -> tuple[MessageRecord, MessageRecord]:
            user = await conv.get_message(user_message_id)
            if user is None:
                raise MessageNotFound(str(user_message_id))
            if user.role != "user":
                raise InvalidGenerationTarget(f"{user_message_id} is not a user message")
            reply = await conv.add_streaming_reply(parent_id=user.id, model=self._settings.model)
            conv.set_leaf(reply.id)
            return user, reply

        return await self._start_generation(conversation_id, start)

    async def switch_branch(self, conversation_id: UUID, message_id: UUID) -> ConversationView:
        """Show the branch through `message_id`: its leaf becomes the current leaf."""
        async with self._repo.locked(conversation_id) as conv:
            if await conv.get_message(message_id) is None:
                raise MessageNotFound(str(message_id))
            refs = await conv.message_refs()
            leaf = resolve_leaf(message_id, _children_by_parent(refs))
            if leaf not in {ref.id for ref in refs}:
                raise RuntimeError(f"resolve_leaf returned {leaf}, not in this conversation")
            conv.set_leaf(leaf)
        return await self.get_conversation(conversation_id)

    async def _start_generation(
        self,
        conversation_id: UUID,
        start: Callable[[LockedConversation], Awaitable[tuple[MessageRecord, MessageRecord]]],
    ) -> Generation:
        token = await self._lock.acquire(conversation_id)
        if token is None:
            raise GenerationInProgress(str(conversation_id))
        try:
            async with self._repo.locked(conversation_id) as conv:
                user, reply = await start(conv)
        except BaseException:
            # Anything failing before streaming starts must not strand the lock.
            await _shielded("release generation lock", self._lock.release(conversation_id, token))
            raise
        return Generation(
            repo=self._repo,
            lock=self._lock,
            provider=self._provider,
            settings=self._settings,
            conversation_id=conversation_id,
            user_message=user,
            assistant_message=reply,
            lock_token=token,
        )
