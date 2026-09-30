"""Who is calling: a Cognito ID token in, a ``users`` row out.

Every route under /api/v1 depends on ``current_user`` - declared once on the
router - so a request gets through only with an ID token that this user pool
signed for this app client and that has not expired. Anything else is a 401.
With no pool configured the answer is 503: a missing setting never leaves the
API open.
"""

import asyncio
import logging
from functools import lru_cache
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings
from app.db import SessionDep
from app.models import User
from app.services import users as users_service

logger = logging.getLogger(__name__)

# auto_error=False: a missing header gets the same 401 as a bad token, below,
# rather than whatever HTTPBearer would raise on its own.
_bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


@lru_cache
def _static_keys(jwks: str) -> jwt.PyJWKSet:
    return jwt.PyJWKSet.from_json(jwks)


@lru_cache
def _key_client(url: str) -> jwt.PyJWKClient:
    # Holds the fetched key set for five minutes, and fetches again when a token
    # names a key id it has not seen - which is how Cognito key rotation arrives.
    return jwt.PyJWKClient(url)


async def _signing_key(token: str, settings: Settings) -> Any:
    """The pool's public key that signed this token."""
    if settings.cognito_jwks:
        # Lambda has no route to the internet, so the deploy hands it the keys.
        kid = jwt.get_unverified_header(token).get("kid")
        try:
            return _static_keys(settings.cognito_jwks)[kid].key
        except KeyError:
            raise _unauthorized("Invalid token") from None

    client = _key_client(f"{settings.cognito_issuer}/.well-known/jwks.json")
    # PyJWKClient fetches with urllib; keep that off the event loop.
    signing_key = await asyncio.to_thread(client.get_signing_key_from_jwt, token)
    return signing_key.key


async def current_user(
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if not settings.auth_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sign-in is not configured",
        )
    if credentials is None:
        raise _unauthorized("Not signed in")

    token = credentials.credentials
    try:
        claims = jwt.decode(
            token,
            await _signing_key(token, settings),
            algorithms=["RS256"],
            audience=settings.cognito_client_id,
            issuer=settings.cognito_issuer,
            options={"require": ["exp", "iss", "aud", "sub", "token_use"]},
        )
    except jwt.PyJWKClientConnectionError as exc:
        logger.warning("could not fetch the user pool's signing keys: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sign-in is unavailable",
        ) from exc
    except jwt.PyJWTError as exc:
        logger.info("rejected token: %s", exc)
        raise _unauthorized("Invalid token") from exc

    # The pool signs access tokens with the same key, but only an ID token says
    # who the person is.
    if claims["token_use"] != "id":
        raise _unauthorized("Invalid token")
    email = claims.get("email")
    if not email:
        raise _unauthorized("Invalid token")
    name = (claims.get("name") or email.split("@", 1)[0])[:120]

    return await users_service.get_or_create(session, sub=claims["sub"], email=email, name=name)


CurrentUser = Annotated[User, Depends(current_user)]
