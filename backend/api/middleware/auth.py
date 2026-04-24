"""JWT authentication middleware.

Supports JWT Bearer tokens (analyst dashboard) and API key headers (bank
integrations). In dev mode, unauthenticated requests pass through.
"""

from __future__ import annotations

import time
from typing import Any

import structlog
from fastapi import Depends, Header, HTTPException, Request, status

from backend.config import get_settings

log = structlog.get_logger()


_jwt_lib: Any = None

try:
    import jwt as _jwt_lib  # type: ignore[no-redef]  # PyJWT
except ImportError:
    # JWT verification won't work without PyJWT, but we don't want to
    # crash on import in environments that don't have it (e.g., some CI).
    _jwt_lib = None


class AuthUser:
    """Represents an authenticated caller."""

    def __init__(self, subject: str, scopes: list[str] | None = None):
        self.subject = subject
        self.scopes = scopes or []

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes or "admin" in self.scopes

    def __repr__(self) -> str:
        return f"AuthUser(sub={self.subject!r}, scopes={self.scopes})"


def _decode_jwt(token: str) -> dict[str, Any]:
    """Decode and verify a JWT token."""
    if _jwt_lib is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT verification unavailable (PyJWT not installed)",
        )

    settings = get_settings()
    try:
        payload = _jwt_lib.decode(
            token,
            settings.api_secret_key,
            algorithms=["HS256"],
        )
        return payload
    except _jwt_lib.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        ) from exc
    except _jwt_lib.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
        ) from exc


def create_token(subject: str, scopes: list[str] | None = None, ttl_seconds: int = 3600) -> str:
    """Create a signed JWT. Used by tests and the (future) auth service."""
    if _jwt_lib is None:
        raise RuntimeError("PyJWT not installed")
    settings = get_settings()
    payload = {
        "sub": subject,
        "scopes": scopes or ["read"],
        "iat": int(time.time()),
        "exp": int(time.time()) + ttl_seconds,
    }
    return _jwt_lib.encode(payload, settings.api_secret_key, algorithm="HS256")



async def require_auth(
    request: Request,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> AuthUser:
    """Dependency that enforces authentication.

    Checks in order:
      1. Authorization: Bearer <jwt>
      2. X-Api-Key: <key>
      3. Dev mode pass-through
    """
    settings = get_settings()

    # 1. JWT bearer
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:]
        payload = _decode_jwt(token)
        user = AuthUser(
            subject=payload.get("sub", "unknown"),
            scopes=payload.get("scopes", []),
        )
        log.debug("auth.jwt_ok", sub=user.subject)
        return user

    # 2. API key (for bank integrations)
    if x_api_key:
        if len(x_api_key) < 16:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key too short",
            )
        # In prod, validate against a table of hashed keys.
        # For now, any key >= 16 chars is accepted.
        # TODO: hash-based API key lookup
        return AuthUser(subject=f"apikey-{x_api_key[:8]}...", scopes=["read", "write"])

    # 3. Dev mode pass-through
    if not settings.is_prod:
        return AuthUser(subject="dev-unauthenticated", scopes=["read", "write", "admin"])

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing Authorization header or X-Api-Key",
    )


async def require_admin(user: AuthUser = Depends(require_auth)) -> AuthUser:
    """Dependency that requires admin scope."""
    if not user.has_scope("admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin scope required",
        )
    return user


# Keep the old function for backwards compat (used by events route)
async def require_api_key(x_api_key: str | None = Header(default=None)) -> str:
    """Legacy API key check — use require_auth for new endpoints."""
    if x_api_key is None:
        settings = get_settings()
        if not settings.is_prod:
            return "dev-unauthenticated"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing api key",
        )
    if len(x_api_key) < 8:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid api key",
        )
    return x_api_key
