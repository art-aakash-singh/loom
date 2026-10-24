from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine


async def add_conversation(engine: AsyncEngine) -> UUID:
    cid = uuid4()
    async with engine.begin() as conn:
        await conn.execute(text("INSERT INTO conversations (id) VALUES (:id)"), {"id": cid})
    return cid


async def add_message(
    engine: AsyncEngine,
    cid: UUID,
    *,
    parent_id: UUID | None = None,
    role: str = "user",
    status: str = "complete",
    stop_reason: str | None = None,
    error_kind: str | None = None,
) -> UUID:
    mid = uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO messages
                    (id, conversation_id, parent_id, role, status, stop_reason, error_kind,
                     created_at, finished_at)
                VALUES
                    (:id, :cid, :parent_id, :role, :status, :stop_reason, :error_kind, now(),
                     CASE WHEN :status = 'streaming' THEN NULL ELSE now() END)
                """
            ),
            {
                "id": mid,
                "cid": cid,
                "parent_id": parent_id,
                "role": role,
                "status": status,
                "stop_reason": stop_reason,
                "error_kind": error_kind,
            },
        )
    return mid


async def test_valid_chain_is_accepted(engine: AsyncEngine) -> None:
    cid = await add_conversation(engine)
    user = await add_message(engine, cid)
    reply = await add_message(
        engine, cid, parent_id=user, role="assistant", status="complete", stop_reason="complete"
    )
    await add_message(engine, cid, parent_id=reply)  # next user turn
    # cancelled, error and streaming assistant rows are valid leaves too
    other = await add_conversation(engine)
    u2 = await add_message(engine, other)
    await add_message(engine, other, parent_id=u2, role="assistant", status="cancelled")
    third = await add_conversation(engine)
    u3 = await add_message(engine, third)
    await add_message(
        engine, third, parent_id=u3, role="assistant", status="error", error_kind="overloaded"
    )
    fourth = await add_conversation(engine)
    u4 = await add_message(engine, fourth)
    await add_message(engine, fourth, parent_id=u4, role="assistant", status="streaming")


async def test_complete_assistant_without_stop_reason_is_rejected(engine: AsyncEngine) -> None:
    cid = await add_conversation(engine)
    user = await add_message(engine, cid)

    with pytest.raises(IntegrityError, match="messages_assistant_complete_iff_stop_reason"):
        await add_message(engine, cid, parent_id=user, role="assistant", status="complete")


async def test_user_message_with_stop_reason_is_rejected(engine: AsyncEngine) -> None:
    cid = await add_conversation(engine)

    with pytest.raises(IntegrityError, match="messages_user_is_plain_complete"):
        await add_message(engine, cid, stop_reason="complete")


async def test_error_message_without_error_kind_is_rejected(engine: AsyncEngine) -> None:
    cid = await add_conversation(engine)
    user = await add_message(engine, cid)

    with pytest.raises(IntegrityError, match="messages_error_iff_error_kind"):
        await add_message(engine, cid, parent_id=user, role="assistant", status="error")


async def test_second_root_is_rejected(engine: AsyncEngine) -> None:
    cid = await add_conversation(engine)
    await add_message(engine, cid)

    with pytest.raises(IntegrityError, match="one_root_per_conversation"):
        await add_message(engine, cid)


async def test_second_child_is_rejected(engine: AsyncEngine) -> None:
    cid = await add_conversation(engine)
    user = await add_message(engine, cid)
    await add_message(
        engine, cid, parent_id=user, role="assistant", status="complete", stop_reason="complete"
    )

    with pytest.raises(IntegrityError, match="one_child_per_parent"):
        await add_message(
            engine, cid, parent_id=user, role="assistant", status="complete", stop_reason="complete"
        )


async def test_parent_in_another_conversation_is_rejected(engine: AsyncEngine) -> None:
    cid = await add_conversation(engine)
    foreign_parent = await add_message(engine, await add_conversation(engine))

    with pytest.raises(IntegrityError, match="messages_parent_fk"):
        await add_message(engine, cid, parent_id=foreign_parent)


async def test_streaming_user_message_is_rejected(engine: AsyncEngine) -> None:
    cid = await add_conversation(engine)

    with pytest.raises(IntegrityError, match="messages_user_is_plain_complete"):
        await add_message(engine, cid, status="streaming")


async def test_unknown_status_is_rejected(engine: AsyncEngine) -> None:
    cid = await add_conversation(engine)

    with pytest.raises(IntegrityError, match="messages_status_check"):
        await add_message(engine, cid, status="done")


async def test_current_leaf_in_another_conversation_is_rejected(engine: AsyncEngine) -> None:
    cid = await add_conversation(engine)
    foreign_leaf = await add_message(engine, await add_conversation(engine))

    # Deferred: the UPDATE itself succeeds, the COMMIT is what fails.
    with pytest.raises(IntegrityError, match="conversations_current_leaf_fk"):
        async with engine.begin() as conn:
            await conn.execute(
                text("UPDATE conversations SET current_leaf_id = :leaf WHERE id = :cid"),
                {"leaf": foreign_leaf, "cid": cid},
            )
