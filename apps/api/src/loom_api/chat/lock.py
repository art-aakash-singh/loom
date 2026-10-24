import secrets
from uuid import UUID

from redis.asyncio import Redis

# Delete only if we still own the lock. A plain DEL could free a lock that expired and
# was re-acquired by another generation in the meantime.
_RELEASE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""


def lock_key(conversation_id: UUID) -> str:
    return f"conv:{conversation_id}:gen"


class GenerationLock:
    """Per-conversation 'one reply at a time' lock. The only Redis user in the chat domain."""

    def __init__(self, redis: Redis, ttl_s: int) -> None:
        self._redis = redis
        self._ttl_s = ttl_s
        self._release_script = redis.register_script(_RELEASE_LUA)

    async def acquire(self, conversation_id: UUID) -> str | None:
        """Return the owner token, or None if another generation holds the lock."""
        token = secrets.token_urlsafe(16)
        acquired = await self._redis.set(lock_key(conversation_id), token, nx=True, ex=self._ttl_s)
        return token if acquired else None

    async def release(self, conversation_id: UUID, token: str) -> bool:
        deleted = await self._release_script(keys=[lock_key(conversation_id)], args=[token])
        return bool(deleted)
