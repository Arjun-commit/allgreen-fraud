"""JWT auth. Stubbed for phase 1 — real implementation in phase 6 (hardening).

Leaving the function signature here so we can wire it into routes early
and just flip the implementation later without touching the call sites.
"""

from fastapi import Header, HTTPException, status


async def require_api_key(x_api_key: str | None = Header(default=None)) -> str:
    # TODO(phase-6): replace with JWT verification + scope checks
    if x_api_key is None:
        return "dev-unauthenticated"
    if len(x_api_key) < 8:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid api key",
        )
    return x_api_key
