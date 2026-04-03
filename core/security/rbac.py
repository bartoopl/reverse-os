"""
Role-Based Access Control.

Roles (hierarchy):
  admin     → full access: manage users, rules, override status, financial
  warehouse → inspect returns, read-only on orders/returns
  viewer    → read-only on returns and stats
  api_key   → machine-to-machine: submit returns, webhooks

Permission matrix:
  Action                        admin  warehouse  viewer  api_key
  ─────────────────────────────────────────────────────────────────
  View returns (list/detail)      ✓       ✓        ✓        –
  Initiate return (portal)        –       –        –        ✓
  Warehouse inspection            ✓       ✓        –        –
  Manual status override          ✓       –        –        –
  Financial (refund/credit)       ✓       –        –        –
  Manage rule sets                ✓       –        –        –
  Manage users                    ✓       –        –        –
  View stats/dashboard            ✓       ✓        ✓        –
  KSeF export                     ✓       –        –        –
  Sync order to platform          ✓       –        –        –
"""
from __future__ import annotations

from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.security.jwt import bearer, decode_token

ROLE_HIERARCHY = {"admin": 4, "warehouse": 3, "viewer": 2, "api_key": 1}


def _get_role_level(role: str) -> int:
    return ROLE_HIERARCHY.get(role, 0)


def require_role(*allowed_roles: str) -> Callable:
    """
    FastAPI dependency factory.
    Usage:  Depends(require_role("admin", "warehouse"))
    """
    async def _check(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
        payload = decode_token(creds.credentials)
        role = payload.get("role", "")
        if role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required roles: {list(allowed_roles)}. Your role: {role!r}",
            )
        return payload
    return _check


def require_min_role(min_role: str) -> Callable:
    """
    Require at least min_role level in hierarchy.
    require_min_role("warehouse") allows admin + warehouse.
    """
    min_level = _get_role_level(min_role)

    async def _check(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
        payload = decode_token(creds.credentials)
        role = payload.get("role", "")
        if _get_role_level(role) < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Minimum role required: {min_role!r}. Your role: {role!r}",
            )
        return payload
    return _check


# Convenience dependencies
IsAdmin     = Depends(require_role("admin"))
IsStaff     = Depends(require_min_role("warehouse"))
IsAnyStaff  = Depends(require_min_role("viewer"))
IsApiKey    = Depends(require_role("api_key"))
