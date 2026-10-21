import asyncio
import logging
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import aclosing

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from loom_api.chat import service
from loom_api.chat.schemas import ChatEvent, ChatRequest
from loom_api.deps import GenerationSettingsDep, ProviderDep

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


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


@router.post(
    "/chat",
    operation_id="postChat",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": "SSE event stream"}},
)
async def post_chat(
    body: ChatRequest, provider: ProviderDep, generation_settings: GenerationSettingsDep
) -> StreamingResponse:
    events = service.stream_reply(provider, generation_settings, body.message)
    return StreamingResponse(
        _sse(events),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
