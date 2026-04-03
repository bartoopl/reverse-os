"""
Server-side session management via Redis.
Sessions are created at token redemption and consumed at return submission.

Security properties:
  - Session ID: 32 bytes CSPRNG (256-bit entropy) — not guessable
  - TTL: 1 hour (configurable) — session expires even if not consumed
  - Single-use: consumed atomically when return is submitted
  - Payload: {order_id, platform, token} — enough to verify and submit
"""
import json
import secrets
from datetime import timedelta

import redis.asyncio as aioredis

from core.config import settings

SESSION_TTL_SECONDS = 3600  # 1 hour
SESSION_PREFIX = "rsession:"


def _client() -> aioredis.Redis:
    return aioredis.from_url(str(settings.REDIS_URL), decode_responses=True)


async def create_session(order_id: str, platform: str, token: str) -> str:
    """
    Store session payload in Redis, return opaque session ID.
    Called after token validity is confirmed (non-consuming check).
    """
    session_id = secrets.token_hex(32)
    payload = json.dumps({"order_id": order_id, "platform": platform, "token": token})

    async with _client() as r:
        await r.setex(f"{SESSION_PREFIX}{session_id}", SESSION_TTL_SECONDS, payload)

    return session_id


async def get_session(session_id: str) -> dict | None:
    """
    Read session without consuming it (for order preview).
    Returns None if expired or not found.
    """
    async with _client() as r:
        raw = await r.get(f"{SESSION_PREFIX}{session_id}")
    if not raw:
        return None
    return json.loads(raw)


async def consume_session(session_id: str) -> dict | None:
    """
    Atomically read and delete session.
    Returns None if already consumed or expired.
    Used at return submission — prevents replay.
    """
    key = f"{SESSION_PREFIX}{session_id}"
    async with _client() as r:
        pipe = r.pipeline()
        pipe.get(key)
        pipe.delete(key)
        raw, _ = await pipe.execute()

    if not raw:
        return None
    return json.loads(raw)
