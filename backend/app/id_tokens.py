"""Checking a Cognito ID token, with nothing else attached.

``app/auth.py`` turns the result into a ``users`` row for the API; the agenda
parser (``app/ai/agenda_lambda.py``) needs only the claims and runs outside the
VPC, so this module imports neither FastAPI nor the database code.
"""

from functools import lru_cache
from typing import Any

import jwt

from app.config import Settings


class InvalidToken(Exception):
    """Missing, malformed, expired or not issued for this app: a 401."""


class KeysUnavailable(Exception):
    """The pool's public keys could not be fetched: a 503, not the caller's fault."""


@lru_cache
def _static_keys(jwks: str) -> jwt.PyJWKSet:
    return jwt.PyJWKSet.from_json(jwks)


@lru_cache
def _key_client(url: str) -> jwt.PyJWKClient:
    # Holds the fetched key set for five minutes, and fetches again when a token
    # names a key id it has not seen - which is how Cognito key rotation arrives.
    return jwt.PyJWKClient(url)


def pool_signing_key(token: str, settings: Settings) -> Any:
    """The user pool's public key that signed this token. Blocking when it fetches."""
    if settings.cognito_jwks:
        # The API's Lambda has no route to the internet, so the deploy hands it the keys.
        try:
            kid = jwt.get_unverified_header(token).get("kid")
            return _static_keys(settings.cognito_jwks)[kid].key
        except KeyError, jwt.PyJWTError:
            raise InvalidToken("unknown signing key") from None

    client = _key_client(f"{settings.cognito_issuer}/.well-known/jwks.json")
    try:
        return client.get_signing_key_from_jwt(token).key
    except jwt.PyJWKClientConnectionError as exc:
        raise KeysUnavailable(str(exc)) from exc
    except jwt.PyJWTError as exc:
        raise InvalidToken(str(exc)) from exc


def decode_id_token(token: str, key: Any, *, audience: str, issuer: str) -> dict[str, Any]:
    """The claims of an ID token signed by ``key`` for ``audience``, or InvalidToken."""
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
            options={"require": ["exp", "iss", "aud", "sub", "token_use"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidToken(str(exc)) from exc
    # The pool signs access tokens with the same key, but only an ID token says
    # who the person is.
    if claims["token_use"] != "id" or not claims.get("email"):
        raise InvalidToken("not an ID token")
    return claims


def verify_pool_token(token: str, settings: Settings) -> dict[str, Any]:
    """The claims of an ID token this user pool signed for this app client."""
    if not settings.auth_configured:
        raise KeysUnavailable("no user pool configured")
    key = pool_signing_key(token, settings)
    return decode_id_token(
        token, key, audience=settings.cognito_client_id, issuer=settings.cognito_issuer
    )
