from uuid import uuid4

from loom_api.chat.lock import GenerationLock, lock_key
from redis.asyncio import Redis


async def test_second_acquire_fails_until_released(lock: GenerationLock) -> None:
    cid = uuid4()

    token = await lock.acquire(cid)
    assert token is not None
    assert await lock.acquire(cid) is None

    assert await lock.release(cid, token) is True
    assert await lock.acquire(cid) is not None


async def test_release_with_wrong_token_does_not_delete_the_lock(
    lock: GenerationLock, redis: Redis
) -> None:
    cid = uuid4()
    token = await lock.acquire(cid)
    assert token is not None

    assert await lock.release(cid, "someone-elses-token") is False

    assert await redis.get(lock_key(cid)) == token.encode()


async def test_lock_expires_so_a_crashed_holder_cannot_block_forever(
    lock: GenerationLock, redis: Redis
) -> None:
    cid = uuid4()
    await lock.acquire(cid)

    assert 0 < await redis.ttl(lock_key(cid)) <= 300
