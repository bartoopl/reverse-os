"""
License key validation system.

Key format:
  REVOS-ENT-{base64url(json_payload)}-{hmac_sha256[:16].upper()}

Payload JSON:
  {
    "cid":      "customer-uuid",
    "tier":     "enterprise" | "starter",
    "max_ret":  500,              # max returns/month (0 = unlimited)
    "exp":      1800000000,       # unix timestamp
    "features": ["auto_refund", "ksef", "rbac", "multi_store"]
  }

Generation (internal tool):
  python -m core.licensing.keygen --cid acme --tier enterprise --max 1000 --exp 2027-01-01

Validation:
  license = LicenseManager.load()
  license.require_feature("auto_refund")
  license.check_return_limit(current_month_count)
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal

from fastapi import HTTPException, status

# Master signing secret — in production, load from HSM / secrets manager
# For key generation only — never shipped in product binary
_MASTER_SECRET_ENV = "REVERSEOS_LICENSE_MASTER"

FREE_TIER_MAX_RETURNS = 100  # per month


@dataclass
class LicensePayload:
    customer_id: str
    tier: Literal["free", "starter", "enterprise"]
    max_returns_per_month: int          # 0 = unlimited
    expires_at: int                      # unix timestamp
    features: list[str] = field(default_factory=list)

    @property
    def is_expired(self) -> bool:
        return self.expires_at > 0 and time.time() > self.expires_at

    @property
    def is_unlimited(self) -> bool:
        return self.max_returns_per_month == 0

    def has_feature(self, feature: str) -> bool:
        return feature in self.features

    def require_feature(self, feature: str) -> None:
        if not self.has_feature(feature):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Feature '{feature}' requires Enterprise license. Visit reverseos.io/upgrade",
            )


class LicenseManager:
    _instance: LicensePayload | None = None

    # Free tier — always available, no key needed
    FREE_TIER = LicensePayload(
        customer_id="free",
        tier="free",
        max_returns_per_month=FREE_TIER_MAX_RETURNS,
        expires_at=0,
        features=[],
    )

    @classmethod
    def load(cls, key: str | None = None) -> LicensePayload:
        """Load and validate license key. Falls back to free tier."""
        if cls._instance:
            return cls._instance

        if not key:
            cls._instance = cls.FREE_TIER
            return cls._instance

        try:
            payload = cls._decode_and_verify(key)
            if payload.is_expired:
                cls._instance = cls.FREE_TIER
            else:
                cls._instance = payload
        except Exception:
            cls._instance = cls.FREE_TIER

        return cls._instance

    @classmethod
    def invalidate_cache(cls) -> None:
        cls._instance = None

    @staticmethod
    def _decode_and_verify(key: str) -> LicensePayload:
        """
        Verify HMAC-SHA256 signature and decode payload.
        Raises ValueError on any verification failure.
        """
        import os
        master_secret = os.environ.get(_MASTER_SECRET_ENV, "dev-secret-change-in-prod")

        parts = key.split("-", 3)
        if len(parts) != 4 or parts[0] != "REVOS" or parts[1] not in ("ENT", "STR"):
            raise ValueError("Invalid key format")

        _, tier_code, payload_b64, provided_sig = parts

        # Verify HMAC
        expected_sig = hmac.new(
            master_secret.encode(),
            f"REVOS-{tier_code}-{payload_b64}".encode(),
            hashlib.sha256,
        ).hexdigest()[:16].upper()

        if not hmac.compare_digest(expected_sig, provided_sig.upper()):
            raise ValueError("Invalid license signature")

        # Decode payload
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        raw = json.loads(base64.urlsafe_b64decode(padded))

        tier_map = {"ENT": "enterprise", "STR": "starter"}
        return LicensePayload(
            customer_id=raw["cid"],
            tier=tier_map[tier_code],
            max_returns_per_month=raw.get("max_ret", 0),
            expires_at=raw.get("exp", 0),
            features=raw.get("features", []),
        )

    @classmethod
    def check_return_limit(cls, current_month_count: int) -> None:
        """Raise 402 if free tier limit exceeded."""
        lic = cls.load()
        if lic.is_unlimited:
            return
        if current_month_count >= lic.max_returns_per_month:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=(
                    f"Monthly return limit reached ({lic.max_returns_per_month}/month). "
                    f"Upgrade at reverseos.io/upgrade"
                ),
            )
