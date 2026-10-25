import asyncio
import logging
from collections.abc import AsyncGenerator, AsyncIterator, Iterator
from contextlib import aclosing, contextmanager
from dataclasses import asdict
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from loom_api.chat.errors import (
    ChatError,
    ConversationNotFound,
    GenerationInProgress,
    InvalidGenerationTarget,
    InvalidParent,
    MessageNotFound,
)
from loom_api.chat.schemas import (
    ChatEvent,
    ConversationDetailOut,
    ConversationOut,
    CreateConversationRequest,
    MessageOut,
    SendMessageRequest,
    SwitchLeafRequest,
)
from loom_api.chat.service import ConversationView, CurrentLeaf, Generation
from loom_api.deps import ChatServiceDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])

_ERRORS: dict[type[ChatError], tuple[int, str]] = {
    ConversationNotFound: (404, "Conversation not found"),
    MessageNotFound: (404, "Message not found in this conversation"),
    GenerationInProgress: (409, "A reply is still generating for this conversation"),
    InvalidParent: (422, "parent_id must be an assistant message of this conversation, or null"),
    InvalidGenerationTarget: (422, "Only a user message can be regenerated"),
}


@contextmanager
def _http_errors() -> Iterator[None]:
    """Map domain errors to HTTP responses; anything else stays a 500."""
    try:
        yield
    except ChatError as exc:
        status_code, detail = _ERRORS[type(exc)]
        raise HTTPException(status_code=status_code, detail=detail) from None


def _responses(*errors: type[ChatError]) -> dict[int | str, dict[str, Any]]:
    return {_ERRORS[e][0]: {"description": _ERRORS[e][1]} for e in errors}


def _detail(view: ConversationView) -> ConversationDetailOut:
    return ConversationDetailOut(
        **ConversationOut.model_validate(view.conversation).model_dump(),
        messages=[
            MessageOut.model_validate({**asdict(m), "sibling_ids": view.sibling_ids[m.id]})
            for m in view.path
        ],
    )


def _stream(generation: Generation) -> StreamingResponse:
    return StreamingResponse(
        _sse(generation.events()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


_SSE_OK: dict[int | str, dict[str, Any]] = {
    200: {"content": {"text/event-stream": {}}, "description": "SSE event stream"}
}


async def _sse(events: AsyncGenerator[ChatEvent]) -> AsyncIterator[str]:
    # aclosing() guarantees the upstream generator (and the provider HTTP stream
    # inside it) is closed even if we are cancelled mid-iteration.
    async with aclosing(events) as stream:
        try:
            async for event in stream:
                yield f"data: {event.model_dump_json()}\n\n"
        except asyncio.CancelledError:
            logger.info("Client disconnected mid-stream; cancelled upstream LLM call")
            raise


@router.post("", operation_id="createConversation", status_code=201)
async def create_conversation(
    service: ChatServiceDep, body: CreateConversationRequest | None = None
) -> ConversationOut:
    title = body.title if body else None
    return ConversationOut.model_validate(await service.create_conversation(title))


@router.get("", operation_id="listConversations")
async def list_conversations(
    service: ChatServiceDep, limit: Annotated[int, Query(ge=1, le=100)] = 50
) -> list[ConversationOut]:
    return [ConversationOut.model_validate(c) for c in await service.list_conversations(limit)]


@router.get(
    "/{conversation_id}",
    operation_id="getConversation",
    responses=_responses(ConversationNotFound),
)
async def get_conversation(conversation_id: UUID, service: ChatServiceDep) -> ConversationDetailOut:
    with _http_errors():
        return _detail(await service.get_conversation(conversation_id))


@router.post(
    "/{conversation_id}/messages",
    operation_id="postMessage",
    response_class=StreamingResponse,
    responses=_SSE_OK | _responses(ConversationNotFound, GenerationInProgress, InvalidParent),
)
async def post_message(
    conversation_id: UUID, body: SendMessageRequest, service: ChatServiceDep
) -> StreamingResponse:
    # Omitted and explicit null differ: omitted continues the conversation, null makes a root.
    parent: UUID | None | CurrentLeaf = (
        body.parent_id if "parent_id" in body.model_fields_set else "current_leaf"
    )
    with _http_errors():
        return _stream(await service.send_message(conversation_id, body.text, parent))


@router.post(
    "/{conversation_id}/messages/{user_message_id}/regenerate",
    operation_id="regenerateMessage",
    response_class=StreamingResponse,
    responses=_SSE_OK
    | _responses(
        ConversationNotFound, MessageNotFound, GenerationInProgress, InvalidGenerationTarget
    ),
)
async def regenerate(
    conversation_id: UUID, user_message_id: UUID, service: ChatServiceDep
) -> StreamingResponse:
    with _http_errors():
        return _stream(await service.regenerate(conversation_id, user_message_id))


@router.put(
    "/{conversation_id}/leaf",
    operation_id="switchBranch",
    responses=_responses(ConversationNotFound, MessageNotFound),
)
async def switch_branch(
    conversation_id: UUID, body: SwitchLeafRequest, service: ChatServiceDep
) -> ConversationDetailOut:
    with _http_errors():
        return _detail(await service.switch_branch(conversation_id, body.message_id))
