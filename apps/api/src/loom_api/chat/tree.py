"""Message-tree navigation. Pure: no DB, no clock (ruff TID251 enforces the imports)."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class ChildRef:
    id: UUID
    created_at: datetime


def resolve_leaf(start_id: UUID, children: Mapping[UUID, Sequence[ChildRef]]) -> UUID:
    """The leaf to show when the user switches to `start_id`: follow the newest child down.

    `children` lists each parent's children oldest first, so the newest is the last. A leaf
    returns itself. Newest is a choice, not the only answer: returning to the branch the
    user last had open below this point needs a remembered position per message, which the
    schema does not store yet. A still-streaming reply counts as a child like any other.
    """
    current = start_id
    seen = {current}
    while kids := children.get(current):
        current = max(kids, key=lambda child: child.created_at).id
        if current in seen:
            raise ValueError(f"message tree has a cycle at {current}")
        seen.add(current)
    return current
