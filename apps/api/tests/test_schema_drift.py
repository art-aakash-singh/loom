import re
from typing import get_args

from loom_api.chat.records import MessageStatus
from loom_api.llm.types import ErrorKind, Role, StopReason
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


def quoted_values(definition: str) -> set[str]:
    return set(re.findall(r"'([^']+)'", definition))


async def test_check_constraints_match_python_enums(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conrelid = 'messages'::regclass AND contype = 'c'"
            )
        )
        definitions = {name: definition for name, definition in rows}  # noqa: C416

    assert quoted_values(definitions["messages_stop_reason_check"]) == set(get_args(StopReason))
    assert quoted_values(definitions["messages_error_kind_check"]) == set(get_args(ErrorKind))
    assert quoted_values(definitions["messages_role_check"]) == set(get_args(Role))
    assert quoted_values(definitions["messages_status_check"]) == set(get_args(MessageStatus))
