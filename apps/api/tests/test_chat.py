import asyncio
import logging
from collections.abc import AsyncGenerator, Sequence
from typing import Any
from uuid import UUID, uuid4

import pytest
from conftest import UseProvider
from httpx import AsyncClient
from loom_api.chat.lock import lock_key
from loom_api.chat.records import MessageRecord
from loom_api.chat.repository import ChatRepository
from loom_api.chat.router import _sse
from loom_api.chat.schemas import ChatEvent, TextDeltaEvent
from loom_api.llm.fake import FakeProvider
from loom_api.llm.types import (
    GenerationSettings,
    Message,
    MessageEnd,
    StreamError,
    StreamEvent,
    TextDelta,
    Usage,
)
from loom_api.main import app
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from support import eventually, parse_sse, post_then_disconnect

FULL_REPLY = "Hello from the fake provider. This is a streamed reply."


class ScriptedProvider:
    def __init__(self, *events: StreamEvent) -> None:
        self._events = events
        self.seen: list[Sequence[Message]] = []

    async def stream(
        self, system: str, messages: Sequence[Message], settings: GenerationSettings
    ) -> AsyncGenerator[StreamEvent]:
        self.seen.append(messages)
        for event in self._events:
            yield event


class GatedProvider:
    """Emits one delta, then waits until the test lets it finish."""

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def stream(
        self, system: str, messages: Sequence[Message], settings: GenerationSettings
    ) -> AsyncGenerator[StreamEvent]:
        yield TextDelta("partial")
        self.started.set()
        await self.release.wait()
        yield MessageEnd("complete", Usage(3, 4))


async def create_conversation(client: AsyncClient) -> UUID:
    response = await client.post("/conversations")
    assert response.status_code == 201
    assert response.json()["current_leaf_id"] is None
    return UUID(response.json()["id"])


async def send(client: AsyncClient, cid: UUID, text: str = "hi") -> tuple[int, str]:
    response = await client.post(f"/conversations/{cid}/messages", json={"text": text})
    return response.status_code, response.text


async def get_conversation(client: AsyncClient, cid: UUID) -> dict[str, Any]:
    response = await client.get(f"/conversations/{cid}")
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


async def get_messages(client: AsyncClient, cid: UUID) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = (await get_conversation(client, cid))["messages"]
    return messages


async def active_path(repo: ChatRepository, cid: UUID) -> list[MessageRecord]:
    conversation = await repo.get_conversation(cid)
    assert conversation is not None
    leaf = conversation.current_leaf_id
    return await repo.path_to(leaf) if leaf else []


async def lock_is_free(redis: Redis, cid: UUID) -> bool:
    return not await redis.exists(lock_key(cid))


async def test_two_turns_form_a_chain_and_advance_the_leaf(
    client: AsyncClient, use_provider: UseProvider
) -> None:
    use_provider(FakeProvider(delay_s=0))
    cid = await create_conversation(client)

    status, body = await send(client, cid, "first")
    events = parse_sse(body)
    await send(client, cid, "second")
    conversation = await get_conversation(client, cid)
    messages = conversation["messages"]

    assert status == 200
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]
    assert messages[0]["parent_id"] is None
    for parent, child in zip(messages, messages[1:], strict=False):
        assert child["parent_id"] == parent["id"]
    assert conversation["current_leaf_id"] == messages[-1]["id"]

    user, assistant = messages[:2]
    assert events[0] == {
        "type": "turn_started",
        "user_message_id": user["id"],
        "assistant_message_id": assistant["id"],
    }
    assert events[-1]["type"] == "message_end"
    assert user["status"] == "complete"
    assert user["content"] == [{"type": "text", "text": "first"}]
    assert user["stop_reason"] is None
    assert assistant["status"] == "complete"
    assert assistant["stop_reason"] == "complete"
    assert assistant["error_kind"] is None
    assert assistant["content"] == [{"type": "text", "text": FULL_REPLY}]
    assert assistant["model"] == "fake"
    assert assistant["usage"] == events[-1]["usage"]
    assert assistant["created_at"] <= assistant["finished_at"]


async def test_history_sent_to_the_provider_is_the_path_to_the_new_user_message(
    client: AsyncClient, use_provider: UseProvider
) -> None:
    provider = ScriptedProvider(TextDelta("ok"), MessageEnd("complete", Usage(1, 1)))
    use_provider(provider)
    cid = await create_conversation(client)

    await send(client, cid, "one")
    await send(client, cid, "two")

    # The new reply's own (empty, streaming) row is not part of its context.
    assert provider.seen[-1] == [
        Message("user", "one"),
        Message("assistant", "ok"),
        Message("user", "two"),
    ]


async def test_stream_error_mid_stream_stores_error_row_with_partial_content(
    client: AsyncClient, use_provider: UseProvider
) -> None:
    use_provider(FakeProvider(fail_with="rate_limited", delay_s=0))
    cid = await create_conversation(client)

    _, body = await send(client, cid)
    _, assistant = await get_messages(client, cid)

    assert parse_sse(body)[-1]["type"] == "error"
    assert assistant["status"] == "error"
    assert assistant["error_kind"] == "rate_limited"
    assert assistant["stop_reason"] is None
    assert assistant["usage"] is None
    assert assistant["finished_at"] is not None
    assert assistant["content"] == [{"type": "text", "text": "Hello from the fake"}]


async def test_stream_error_before_first_delta_stores_error_row_with_empty_content(
    client: AsyncClient, use_provider: UseProvider
) -> None:
    use_provider(ScriptedProvider(StreamError("overloaded", "busy")))
    cid = await create_conversation(client)

    await send(client, cid)
    _, assistant = await get_messages(client, cid)

    assert assistant["status"] == "error"
    assert assistant["error_kind"] == "overloaded"
    assert assistant["content"] == []


async def test_provider_ending_without_terminal_event_is_recorded_as_error(
    client: AsyncClient, use_provider: UseProvider
) -> None:
    use_provider(ScriptedProvider(TextDelta("cut off")))
    cid = await create_conversation(client)

    _, body = await send(client, cid)
    _, assistant = await get_messages(client, cid)

    assert parse_sse(body)[-1]["kind"] == "unexpected"
    assert assistant["status"] == "error"
    assert assistant["error_kind"] == "unexpected"
    assert assistant["content"] == [{"type": "text", "text": "cut off"}]


async def test_client_disconnect_mid_stream_stores_cancelled_row_with_partial_content(
    client: AsyncClient, use_provider: UseProvider, repo: ChatRepository
) -> None:
    use_provider(FakeProvider(delay_s=0.05))
    cid = await create_conversation(client)

    chunks = await post_then_disconnect(
        app, f"/conversations/{cid}/messages", {"text": "hi"}, after_chunks=3
    )

    async def finalized() -> bool:
        return (await active_path(repo, cid))[-1].status != "streaming"

    assert await eventually(finalized), "assistant row still streaming after disconnect"
    user, assistant = await active_path(repo, cid)
    assert chunks >= 3
    assert assistant.status == "cancelled"
    assert assistant.parent_id == user.id
    assert assistant.stop_reason is None
    assert assistant.error_kind is None
    assert assistant.finished_at is not None
    (block,) = assistant.content
    assert block["text"].startswith("Hello from")
    assert block["text"] != FULL_REPLY


async def test_cancellation_propagates_out_of_the_generation(
    client: AsyncClient, use_provider: UseProvider, repo: ChatRepository, redis: Redis
) -> None:
    provider = GatedProvider()
    service = use_provider(provider)
    cid = await create_conversation(client)
    generation = await service.send_message(cid, "hi")

    async def consume() -> None:
        async for _ in generation.events():
            pass

    task = asyncio.create_task(consume())
    await asyncio.wait_for(provider.started.wait(), timeout=3)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task  # never swallowed

    _, assistant = await active_path(repo, cid)
    assert assistant.status == "cancelled"
    assert assistant.content == [{"type": "text", "text": "partial"}]
    assert await lock_is_free(redis, cid)


async def test_concurrent_send_gets_409_while_a_reply_is_streaming(
    client: AsyncClient, use_provider: UseProvider, redis: Redis, repo: ChatRepository
) -> None:
    provider = GatedProvider()
    use_provider(provider)
    cid = await create_conversation(client)

    first = asyncio.create_task(send(client, cid, "first"))
    await asyncio.wait_for(provider.started.wait(), timeout=3)

    status, _ = await send(client, cid, "second")
    assert status == 409
    in_flight = await active_path(repo, cid)
    assert [(m.role, m.status) for m in in_flight] == [
        ("user", "complete"),
        ("assistant", "streaming"),
    ]

    provider.release.set()
    first_status, _ = await first
    assert first_status == 200
    messages = await get_messages(client, cid)
    assert [(m["role"], m["status"]) for m in messages] == [
        ("user", "complete"),
        ("assistant", "complete"),
    ]
    assert await lock_is_free(redis, cid)


async def test_concurrent_turn_starts_queue_on_the_row_lock_instead_of_branching(
    repo: ChatRepository,
) -> None:
    """Below the Redis lock: if it ever lets two sends through (TTL expiry, Redis failover),
    SELECT ... FOR UPDATE must still produce one linear chain."""
    cid = (await repo.create_conversation()).id

    turns = await asyncio.gather(*(repo.start_turn(cid, f"q{i}", model="fake") for i in range(5)))

    path = await active_path(repo, cid)
    assert len(path) == 10
    assert [m.role for m in path] == ["user", "assistant"] * 5
    for parent, child in zip(path, path[1:], strict=False):
        assert child.parent_id == parent.id
    # Each later turn's user message hangs off the previous turn's reply.
    replies = {assistant.id for _, assistant in turns}
    assert all(m.parent_id in replies for m in path[2::2])


async def test_get_returns_only_the_active_path_in_order(
    client: AsyncClient, use_provider: UseProvider, engine: AsyncEngine
) -> None:
    use_provider(FakeProvider(delay_s=0))
    cid = await create_conversation(client)
    await send(client, cid, "one")
    await send(client, cid, "two")
    first_user, first_reply, *_ = await get_messages(client, cid)

    # Point the leaf back at the first reply: the second turn is now off the active path.
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE conversations SET current_leaf_id = :leaf WHERE id = :cid"),
            {"leaf": UUID(first_reply["id"]), "cid": cid},
        )

    messages = await get_messages(client, cid)
    assert [m["id"] for m in messages] == [first_user["id"], first_reply["id"]]


async def test_startup_sweep_closes_stuck_streaming_rows(
    client: AsyncClient,
    use_provider: UseProvider,
    repo: ChatRepository,
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = use_provider(FakeProvider(delay_s=0))
    cid = (await repo.create_conversation()).id
    _, stuck = await repo.start_turn(cid, "the process died here", model="fake")
    healthy = await create_conversation(client)
    await send(client, healthy)

    with caplog.at_level(logging.INFO, logger="loom_api.chat.service"):
        swept = await service.sweep_interrupted_generations()

    assert swept == 1
    assert "marked 1 interrupted" in caplog.text
    _, assistant = await active_path(repo, cid)
    assert assistant.id == stuck.id
    assert assistant.status == "error"
    assert assistant.error_kind == "unexpected"
    assert assistant.finished_at is not None
    assert (await get_messages(client, healthy))[-1]["status"] == "complete"
    assert await service.sweep_interrupted_generations() == 0


async def test_finalize_does_not_overwrite_a_swept_row(repo: ChatRepository) -> None:
    cid = (await repo.create_conversation()).id
    _, assistant = await repo.start_turn(cid, "hi", model="fake")
    await repo.fail_streaming_messages()

    written = await repo.finalize_assistant(
        assistant.id,
        status="complete",
        content=[{"type": "text", "text": "late"}],
        stop_reason="complete",
        error_kind=None,
        usage=Usage(1, 1),
    )

    assert not written
    assert (await active_path(repo, cid))[-1].status == "error"


async def test_lock_is_released_after_success(
    client: AsyncClient, use_provider: UseProvider, redis: Redis
) -> None:
    use_provider(FakeProvider(delay_s=0))
    cid = await create_conversation(client)

    await send(client, cid)

    assert await lock_is_free(redis, cid)
    assert (await send(client, cid))[0] == 200  # and a follow-up is accepted


async def test_lock_is_released_after_failure(
    client: AsyncClient, use_provider: UseProvider, redis: Redis
) -> None:
    use_provider(FakeProvider(fail_with="overloaded", delay_s=0))
    cid = await create_conversation(client)

    await send(client, cid)

    assert await lock_is_free(redis, cid)


async def test_lock_is_released_after_cancellation(
    client: AsyncClient, use_provider: UseProvider, redis: Redis
) -> None:
    use_provider(FakeProvider(delay_s=0.05))
    cid = await create_conversation(client)

    await post_then_disconnect(
        app, f"/conversations/{cid}/messages", {"text": "hi"}, after_chunks=3
    )

    assert await eventually(lambda: lock_is_free(redis, cid)), "lock still held after disconnect"


async def test_unknown_conversation_is_404_and_leaves_no_lock(
    client: AsyncClient, use_provider: UseProvider, redis: Redis
) -> None:
    use_provider(FakeProvider(delay_s=0))
    missing = uuid4()

    assert (await client.get(f"/conversations/{missing}")).status_code == 404
    assert (await send(client, missing))[0] == 404
    assert await lock_is_free(redis, missing)


async def test_empty_message_is_rejected(client: AsyncClient, use_provider: UseProvider) -> None:
    use_provider(FakeProvider(delay_s=0))
    cid = await create_conversation(client)

    assert (await send(client, cid, ""))[0] == 422


async def test_history_load_failure_closes_the_reply_and_frees_the_lock(
    client: AsyncClient,
    use_provider: UseProvider,
    repo: ChatRepository,
    redis: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = use_provider(FakeProvider(delay_s=0))
    cid = await create_conversation(client)
    real_path_to = repo.path_to

    async def broken_path_to(_: UUID) -> list[MessageRecord]:
        raise RuntimeError("database is down")

    monkeypatch.setattr(repo, "path_to", broken_path_to)
    with pytest.raises(RuntimeError):
        await service.send_message(cid, "hi")
    monkeypatch.setattr(repo, "path_to", real_path_to)

    _, assistant = await active_path(repo, cid)
    assert assistant.status == "error"
    assert assistant.error_kind == "unexpected"
    assert await lock_is_free(redis, cid)


async def test_failed_finalize_is_logged_not_raised_and_lock_is_released(
    client: AsyncClient,
    use_provider: UseProvider,
    repo: ChatRepository,
    redis: Redis,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = use_provider(FakeProvider(delay_s=0))
    cid = await create_conversation(client)

    async def broken_finalize(*_: Any, **__: Any) -> None:
        raise RuntimeError("database is down")

    monkeypatch.setattr(repo, "finalize_assistant", broken_finalize)

    generation = await service.send_message(cid, "hi")
    with caplog.at_level(logging.ERROR, logger="loom_api.chat.service"):
        events = [e async for e in generation.events()]  # must not raise

    assert events[-1].type == "message_end"
    assert "finalize assistant message" in caplog.text
    assert await lock_is_free(redis, cid)


async def test_sse_logs_disconnect_and_closes_upstream(caplog: pytest.LogCaptureFixture) -> None:
    closed = False
    started = asyncio.Event()

    async def endless() -> AsyncGenerator[ChatEvent]:
        nonlocal closed
        try:
            while True:
                await asyncio.sleep(0.01)
                yield TextDeltaEvent(text="x")
        finally:
            closed = True

    async def consume() -> None:
        async for _ in _sse(endless()):
            started.set()

    with caplog.at_level(logging.INFO, logger="loom_api.chat.router"):
        task = asyncio.create_task(consume())
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert closed
    assert "Client disconnected" in caplog.text


async def test_conversation_can_be_created_with_a_title(
    client: AsyncClient, use_provider: UseProvider
) -> None:
    use_provider(FakeProvider(delay_s=0))
    titled = await client.post("/conversations", json={"title": "  Trip plans  "})
    blank = await client.post("/conversations", json={"title": "   "})
    no_body = await client.post("/conversations")
    too_long = await client.post("/conversations", json={"title": "x" * 201})

    assert titled.status_code == 201
    assert titled.json()["title"] == "Trip plans"
    assert blank.json()["title"] is None
    assert no_body.json()["title"] is None
    assert too_long.status_code == 422


async def test_list_puts_the_most_recently_active_conversation_first(
    client: AsyncClient, use_provider: UseProvider
) -> None:
    use_provider(FakeProvider(delay_s=0))
    older = UUID((await client.post("/conversations", json={"title": "older"})).json()["id"])
    await client.post("/conversations", json={"title": "newer"})

    before = (await client.get("/conversations")).json()
    await send(client, older)  # a new turn bumps updated_at
    after = (await client.get("/conversations")).json()

    assert [c["title"] for c in before] == ["newer", "older"]
    assert [c["title"] for c in after] == ["older", "newer"]
    assert "messages" not in after[0]
    assert len((await client.get("/conversations", params={"limit": 1})).json()) == 1
