import asyncio
import logging
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import aclosing
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from loom_api.chat.errors import ConversationNotFound, GenerationInProgress
from loom_api.chat.schemas import (
    ChatEvent,
    ConversationDetailOut,
    ConversationOut,
    CreateConversationRequest,
    MessageOut,
    SendMessageRequest,
)
from loom_api.deps import ChatServiceDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])

_NOT_FOUND = HTTPException(status_code=404, detail="Conversation not found")


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
    responses={404: {"description": "Conversation not found"}},
)
async def get_conversation(conversation_id: UUID, service: ChatServiceDep) -> ConversationDetailOut:
    try:
        conversation, messages = await service.get_conversation(conversation_id)
    except ConversationNotFound:
        raise _NOT_FOUND from None
    return ConversationDetailOut(
        **ConversationOut.model_validate(conversation).model_dump(),
        messages=[MessageOut.model_validate(m) for m in messages],
    )


@router.post(
    "/{conversation_id}/messages",
    operation_id="postMessage",
    response_class=StreamingResponse,
    responses={
        200: {"content": {"text/event-stream": {}}, "description": "SSE event stream"},
        404: {"description": "Conversation not found"},
        409: {"description": "A reply is still generating for this conversation"},
    },
)
async def post_message(
    conversation_id: UUID, body: SendMessageRequest, service: ChatServiceDep
) -> StreamingResponse:
    try:
        generation = await service.send_message(conversation_id, body.text)
    except ConversationNotFound:
        raise _NOT_FOUND from None
    except GenerationInProgress:
        raise HTTPException(
            status_code=409, detail="A reply is still generating for this conversation"
        ) from None
    return StreamingResponse(
        _sse(generation.events()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
