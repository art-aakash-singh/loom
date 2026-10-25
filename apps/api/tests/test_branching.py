"""M5: edit, regenerate and branch switching on the message tree."""

from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID, uuid4

import pytest
from conftest import UseProvider
from httpx import AsyncClient
from loom_api.chat.tree import ChildRef
from loom_api.context.types import ContextInput, ProviderRequest
from redis.asyncio import Redis
from support import (
    create_conversation,
    get_conversation,
    get_messages,
    lock_is_free,
    ok_provider,
    parse_sse,
    passthrough_build,
    regenerate,
    send,
)


@pytest.fixture
def seen_paths(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """The text of every message gather handed to build, one list per turn."""
    seen: list[list[str]] = []

    def capturing_build(inp: ContextInput) -> ProviderRequest:
        seen.append(["".join(b["text"] for b in m.content) for m in inp.path])
        return passthrough_build(inp)

    monkeypatch.setattr("loom_api.chat.service.build", capturing_build)
    return seen


async def two_turns(client: AsyncClient) -> tuple[UUID, list[dict[str, Any]]]:
    cid = await create_conversation(client)
    await send(client, cid, "one")
    await send(client, cid, "two")
    return cid, await get_messages(client, cid)


async def test_edit_creates_a_sibling_and_the_reply_sees_only_the_new_branch(
    client: AsyncClient, use_provider: UseProvider, seen_paths: list[list[str]]
) -> None:
    use_provider(ok_provider())
    cid, (u1, a1, u2, a2) = await two_turns(client)

    status, body = await send(client, cid, "two, edited", parent_id=u2["parent_id"])
    conversation = await get_conversation(client, cid)
    path = conversation["messages"]

    assert status == 200
    assert seen_paths[-1] == ["one", "ok", "two, edited"]  # "two" and its reply are gone
    assert [m["id"] for m in path[:2]] == [u1["id"], a1["id"]]
    edited, reply = path[2:]
    assert edited["content"] == [{"type": "text", "text": "two, edited"}]
    assert edited["parent_id"] == a1["id"]
    assert edited["sibling_ids"] == [u2["id"], edited["id"]]
    assert reply["parent_id"] == edited["id"]
    assert conversation["current_leaf_id"] == reply["id"]
    assert parse_sse(body)[0]["user_message_id"] == edited["id"]


async def test_editing_the_first_message_creates_a_second_root(
    client: AsyncClient, use_provider: UseProvider, seen_paths: list[list[str]]
) -> None:
    use_provider(ok_provider())
    cid, (u1, *_) = await two_turns(client)

    await send(client, cid, "one, edited", parent_id=None)
    path = await get_messages(client, cid)

    assert seen_paths[-1] == ["one, edited"]
    assert len(path) == 2
    assert path[0]["parent_id"] is None
    assert path[0]["sibling_ids"] == [u1["id"], path[0]["id"]]


async def test_regenerate_creates_a_sibling_reply_under_the_same_user_message(
    client: AsyncClient, use_provider: UseProvider, seen_paths: list[list[str]]
) -> None:
    use_provider(ok_provider())
    cid, (u1, a1, u2, a2) = await two_turns(client)

    status, body = await regenerate(client, cid, u2["id"])
    conversation = await get_conversation(client, cid)
    path = conversation["messages"]

    assert status == 200
    events = parse_sse(body)
    assert events[0]["user_message_id"] == u2["id"]
    assert events[-1]["type"] == "message_end"
    assert seen_paths[-1] == ["one", "ok", "two"]  # ends at the user message, not a2
    assert [m["id"] for m in path[:3]] == [u1["id"], a1["id"], u2["id"]]
    new_reply = path[3]
    assert new_reply["id"] == events[0]["assistant_message_id"]
    assert new_reply["parent_id"] == u2["id"]
    assert new_reply["sibling_ids"] == [a2["id"], new_reply["id"]]
    assert conversation["current_leaf_id"] == new_reply["id"]


async def test_regenerate_rejects_anything_but_a_user_message_of_this_conversation(
    client: AsyncClient, use_provider: UseProvider, redis: Redis
) -> None:
    use_provider(ok_provider())
    cid, (u1, a1, *_) = await two_turns(client)
    other, (other_user, *_) = await two_turns(client)

    assert (await regenerate(client, cid, a1["id"]))[0] == 422
    assert (await regenerate(client, cid, str(uuid4())))[0] == 404
    assert (await regenerate(client, cid, other_user["id"]))[0] == 404
    assert (await regenerate(client, uuid4(), u1["id"]))[0] == 404
    assert await lock_is_free(redis, cid)
    assert len(await get_messages(client, cid)) == 4  # nothing was written


async def test_parent_id_must_be_an_assistant_message_of_this_conversation(
    client: AsyncClient, use_provider: UseProvider, redis: Redis
) -> None:
    use_provider(ok_provider())
    cid, (u1, *_) = await two_turns(client)
    _, (_, other_reply, *_) = await two_turns(client)

    for bad_parent in (u1["id"], other_reply["id"], str(uuid4())):
        status, _ = await send(client, cid, "x", parent_id=bad_parent)
        assert status == 422
    assert await lock_is_free(redis, cid)
    assert len(await get_messages(client, cid)) == 4


async def test_switch_sets_the_leaf_to_whatever_resolve_leaf_returns(
    client: AsyncClient, use_provider: UseProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_provider(ok_provider())
    cid, (u1, a1, u2, a2) = await two_turns(client)
    await send(client, cid, "two, edited", parent_id=a1["id"])
    calls: list[tuple[UUID, Mapping[UUID, Sequence[ChildRef]]]] = []

    def fake_resolve_leaf(start_id: UUID, children: Mapping[UUID, Sequence[ChildRef]]) -> UUID:
        calls.append((start_id, children))
        return UUID(a2["id"])

    monkeypatch.setattr("loom_api.chat.service.resolve_leaf", fake_resolve_leaf)

    response = await client.put(f"/conversations/{cid}/leaf", json={"message_id": u2["id"]})

    assert response.status_code == 200
    body = response.json()
    assert body["current_leaf_id"] == a2["id"]
    assert [m["id"] for m in body["messages"]] == [u1["id"], a1["id"], u2["id"], a2["id"]]
    assert body["messages"][2]["sibling_ids"][0] == u2["id"]
    assert (await get_conversation(client, cid))["current_leaf_id"] == a2["id"]

    (start_id, children), *_ = calls
    assert start_id == UUID(u2["id"])
    assert [c.id for c in children[UUID(a1["id"])]][0] == UUID(u2["id"])  # oldest first
    assert len(children[UUID(a1["id"])]) == 2
    assert UUID(u1["id"]) in children  # the root has children...
    assert all(UUID(u1["id"]) != c.id for kids in children.values() for c in kids)  # ...no parent


async def test_switch_refuses_a_leaf_from_another_conversation(
    client: AsyncClient, use_provider: UseProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_provider(ok_provider())
    cid, (u1, *_) = await two_turns(client)
    _, (*_, foreign_leaf) = await two_turns(client)
    monkeypatch.setattr("loom_api.chat.service.resolve_leaf", lambda *_: UUID(foreign_leaf["id"]))

    with pytest.raises(RuntimeError, match="not in this conversation"):
        await client.put(f"/conversations/{cid}/leaf", json={"message_id": u1["id"]})


async def test_switch_to_an_unknown_message_is_404(
    client: AsyncClient, use_provider: UseProvider
) -> None:
    use_provider(ok_provider())
    cid, _ = await two_turns(client)

    missing = await client.put(f"/conversations/{cid}/leaf", json={"message_id": str(uuid4())})
    no_conversation = await client.put(
        f"/conversations/{uuid4()}/leaf", json={"message_id": str(uuid4())}
    )

    assert missing.status_code == 404
    assert no_conversation.status_code == 404


async def test_sibling_ids_on_a_branched_path(
    client: AsyncClient, use_provider: UseProvider
) -> None:
    use_provider(ok_provider())
    cid, (u1, a1, u2, a2) = await two_turns(client)
    await regenerate(client, cid, u2["id"])
    await regenerate(client, cid, u2["id"])
    await send(client, cid, "two, edited", parent_id=a1["id"])

    path = await get_messages(client, cid)

    assert [len(m["sibling_ids"]) for m in path] == [1, 1, 2, 1]
    assert path[2]["sibling_ids"] == [u2["id"], path[2]["id"]]
    assert a2["id"] not in {m["id"] for m in path}  # the old branch is off the path
