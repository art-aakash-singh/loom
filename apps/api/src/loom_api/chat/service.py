import asyncio
import logging
from collections.abc import AsyncGenerator, Awaitable
from contextlib import aclosing
from uuid import UUID

import anyio

from loom_api.chat.context import build_context
from loom_api.chat.errors import ConversationNotFound, GenerationInProgress
from loom_api.chat.lock import GenerationLock
from loom_api.chat.records import ContentBlock, ConversationRecord, FinalStatus, MessageRecord
from loom_api.chat.repository import ChatRepository
from loom_api.chat.schemas import (
    ChatEvent,
    ErrorEvent,
    MessageEndEvent,
    TextDeltaEvent,
    TurnStartedEvent,
    UsageOut,
)
from loom_api.llm.base import LLMProvider
from loom_api.llm.types import (
    RETRYABLE,
    ErrorKind,
    GenerationSettings,
    Message,
    MessageEnd,
    StopReason,
    StreamError,
    TextDelta,
    Usage,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = "You are Loom, a concise and helpful assistant."

# Budget for each cleanup step that runs after cancellation (DB write, lock release).
_CLEANUP_TIMEOUT_S = 5


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
        context: list[Message],
        lock_token: str,
    ) -> None:
        self._repo = repo
        self._lock = lock
        self._provider = provider
        self._settings = settings
        self._conversation_id = conversation_id
        self._context = context
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
                stream = self._provider.stream(SYSTEM_PROMPT, self._context, self._settings)
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
            except Exception:
                logger.exception("Generation failed unexpectedly")
                status, error_kind = "error", "unexpected"
                yield ErrorEvent(
                    kind="unexpected", message="Unexpected error while generating", retryable=False
                )
        finally:
            await _shielded(
                "finalize assistant message",
                self._repo.finalize_assistant(
                    self.assistant_message.id,
                    status=status,
                    content=_text_content(parts),
                    stop_reason=stop_reason,
                    error_kind=error_kind,
                    usage=usage,
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

    async def get_conversation(
        self, conversation_id: UUID
    ) -> tuple[ConversationRecord, list[MessageRecord]]:
        """The conversation and its active path (root → current leaf)."""
        conversation = await self._repo.get_conversation(conversation_id)
        if conversation is None:
            raise ConversationNotFound(str(conversation_id))
        if conversation.current_leaf_id is None:
            return conversation, []
        return conversation, await self._repo.path_to(conversation.current_leaf_id)

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

    async def send_message(self, conversation_id: UUID, text: str) -> Generation:
        """Lock, store the turn, and prepare the reply. Stream it with `.events()`."""
        token = await self._lock.acquire(conversation_id)
        if token is None:
            raise GenerationInProgress(str(conversation_id))
        try:
            user, assistant = await self._repo.start_turn(
                conversation_id, text, model=self._settings.model
            )
        except BaseException:
            # Anything failing before streaming starts must not strand the lock.
            await _shielded("release generation lock", self._lock.release(conversation_id, token))
            raise

        try:
            context = await self._load_history(user.id)
        except BaseException as exc:
            # The reply row exists now, so close it too or it stays 'streaming' until restart.
            cancelled = isinstance(exc, asyncio.CancelledError)
            await _shielded(
                "finalize assistant message",
                self._repo.finalize_assistant(
                    assistant.id,
                    status="cancelled" if cancelled else "error",
                    content=[],
                    stop_reason=None,
                    error_kind=None if cancelled else "unexpected",
                    usage=None,
                ),
            )
            await _shielded("release generation lock", self._lock.release(conversation_id, token))
            raise

        return Generation(
            repo=self._repo,
            lock=self._lock,
            provider=self._provider,
            settings=self._settings,
            conversation_id=conversation_id,
            user_message=user,
            assistant_message=assistant,
            context=context,
            lock_token=token,
        )

    async def _load_history(self, user_message_id: UUID) -> list[Message]:
        """M2a history: everything from the root to the new user message.

        Isolated on purpose: M3 replaces this with the real context builder.
        """
        return build_context(await self._repo.path_to(user_message_id))
