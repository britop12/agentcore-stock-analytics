"""Cognito JWT authentication middleware for FastAPI."""
from __future__ import annotations

import logging
import os
from typing import Any

import json
import urllib.request

from jose import ExpiredSignatureError, JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Module-level JWKS cache: maps kid -> key dict
_jwks_cache: dict[str, Any] = {}


def _get_jwks_uri() -> str:
    region = os.environ["COGNITO_REGION"]
    pool_id = os.environ["COGNITO_USER_POOL_ID"]
    return f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/jwks.json"


def _fetch_jwks() -> dict[str, Any]:
    """Fetch JWKS from Cognito and return a kid-keyed dict."""
    uri = _get_jwks_uri()
    with urllib.request.urlopen(uri, timeout=10) as resp:  # noqa: S310
        keys = json.loads(resp.read()).get("keys", [])
    return {key["kid"]: key for key in keys}


def _get_key(kid: str) -> Any:
    """Return the JWK for the given kid, refreshing the cache if needed."""
    global _jwks_cache
    if kid not in _jwks_cache:
        _jwks_cache = _fetch_jwks()
    return _jwks_cache.get(kid)


def _unauthorized(detail: str) -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": detail})


class AuthMiddleware(BaseHTTPMiddleware):
    """Validate Cognito JWT tokens on every incoming request."""

    async def dispatch(self, request: Request, call_next):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return _unauthorized("Missing or malformed Authorization header")

        token = auth_header[len("Bearer "):]

        try:
            # Peek at the header to get the kid without full verification
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            if not kid:
                return _unauthorized("Token header missing kid")

            key = _get_key(kid)
            if key is None:
                return _unauthorized("Unknown token signing key")

            audience = os.environ["COGNITO_APP_CLIENT_ID"]
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=audience,
            )
        except ExpiredSignatureError:
            return _unauthorized("Token has expired")
        except JWTError as exc:
            logger.debug("JWT validation failed: %s", exc)
            return _unauthorized("Invalid token")
        except Exception as exc:
            logger.warning("Unexpected error during JWT validation: %s", exc)
            return _unauthorized("Token validation error")

        request.state.user = claims
        return await call_next(request)
