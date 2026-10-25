from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from loom_api.chat.tree import ChildRef, resolve_leaf

T0 = datetime(2026, 10, 25, tzinfo=UTC)


def ref(minutes: int) -> ChildRef:
    return ChildRef(id=uuid4(), created_at=T0 + timedelta(minutes=minutes))


def test_a_leaf_resolves_to_itself() -> None:
    leaf = uuid4()
    assert resolve_leaf(leaf, {}) == leaf


def test_follows_the_newest_child_at_every_level() -> None:
    start = uuid4()
    old_reply, new_reply = ref(1), ref(2)
    old_next, new_next = ref(3), ref(4)
    children: dict[UUID, list[ChildRef]] = {
        start: [old_reply, new_reply],
        new_reply.id: [old_next, new_next],
        old_reply.id: [ref(5)],  # newer, but on the branch not taken
    }
    assert resolve_leaf(start, children) == new_next.id


def test_picks_by_created_at_even_if_the_list_is_out_of_order() -> None:
    start, older, newer = uuid4(), ref(1), ref(2)
    assert resolve_leaf(start, {start: [newer, older]}) == newer.id


def test_a_cycle_is_an_error_not_a_hang() -> None:
    a, b = ref(1), ref(2)
    with pytest.raises(ValueError, match="cycle"):
        resolve_leaf(a.id, {a.id: [b], b.id: [a]})
