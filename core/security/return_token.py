"""
One-time return tokens with TTL.

Flow:
  1. Merchant system (or email trigger) calls generate_token(order_id, platform)
  2. Token embedded in deep link: /return?orderId=X&platform=shopify&token=T
  3. Portal calls verify_and_consume_token() — single use, expires after TTL
  4. Token marked used=true → subsequent requests rejected

Security properties:
  - 32 bytes of CSPRNG entropy (256 bits) — not guessable
  - Expires after TTL (default: 7 days)
  - Single-use: consumed on first successful verification
  - No PII in token value itself
"""
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

DEFAULT_TTL_DAYS = 7


async def generate_token(
    db: AsyncSession,
    order_id: str,
    platform: str,
    ttl_days: int = DEFAULT_TTL_DAYS,
) -> str:
    token = secrets.token_hex(32)  # 64-char hex, 256-bit entropy
    expires_at = datetime.now(timezone.utc) + timedelta(days=ttl_days)

    await db.execute(
        text("""
            INSERT INTO return_tokens (token, order_id, platform, expires_at)
            VALUES (:token, :order_id, :platform, :expires_at)
        """),
        {"token": token, "order_id": order_id, "platform": platform, "expires_at": expires_at},
    )
    return token


async def verify_and_consume_token(
    db: AsyncSession,
    order_id: str,
    platform: str,
    token: str,
) -> bool:
    """
    Atomically verify and consume the token.
    Returns False if: not found, wrong order, expired, or already used.
    """
    result = await db.execute(
        text("""
            UPDATE return_tokens
            SET used = true
            WHERE token      = :token
              AND order_id   = :order_id
              AND platform   = :platform
              AND used       = false
              AND expires_at > NOW()
            RETURNING token
        """),
        {"token": token, "order_id": order_id, "platform": platform},
    )
    return result.fetchone() is not None
