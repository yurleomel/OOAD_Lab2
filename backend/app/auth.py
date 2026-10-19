"""Who is calling: a Cognito ID token in, a ``users`` row out.

Every route under /api/v1 depends on ``current_user`` - declared once on the
router - so a request gets through only with an ID token that this user pool
signed for this app client and that has not expired. Anything else is a 401.
With no pool configured the answer is 503: a missing setting never leaves the
API open. The token checks themselves live in ``app/id_tokens.py``, shared with
the agenda parser.
"""

import asyncio
import logging
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app import dev_auth
from app.config import Settings, get_settings
from app.db import SessionDep
from app.id_tokens import InvalidToken, KeysUnavailable, decode_id_token, verify_pool_token
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


async def current_user(
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    local = settings.local_sign_in
    if not (settings.auth_configured or local):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sign-in is not configured",
        )
    if credentials is None:
        raise _unauthorized("Not signed in")

    token = credentials.credentials
    try:
        # Local development trusts its own key (app/dev_auth.py); everything
        # else only the user pool. The claim checks are the same for both.
        if local:
            claims = decode_id_token(
                token,
                dev_auth.signing_key().public_key(),
                audience=dev_auth.AUDIENCE,
                issuer=dev_auth.ISSUER,
            )
        else:
            # The key download, when there is one, uses urllib; keep it off the event loop.
            claims = await asyncio.to_thread(verify_pool_token, token, settings)
    except KeysUnavailable as exc:
        logger.warning("could not fetch the user pool's signing keys: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sign-in is unavailable",
        ) from exc
    except InvalidToken as exc:
        logger.info("rejected token: %s", exc)
        raise _unauthorized("Invalid token") from exc

    email = claims["email"]
    name = (claims.get("name") or email.split("@", 1)[0])[:120]

    return await users_service.get_or_create(session, sub=claims["sub"], email=email, name=name)


CurrentUser = Annotated[User, Depends(current_user)]
