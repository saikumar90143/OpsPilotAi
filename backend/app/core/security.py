"""Password hashing (Argon2id), JWT access tokens, and opaque token helpers."""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import Settings
from app.core.errors import UnauthorizedError

ACCESS_TOKEN_TYPE = "access"
OPAQUE_TOKEN_BYTES = 32
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128

_password_hasher = PasswordHasher()


def hash_password(plain_password: str) -> str:
    """Hash a password with Argon2id."""
    return _password_hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plaintext password against an Argon2id hash (constant-time)."""
    try:
        return _password_hasher.verify(password_hash, plain_password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _password_hasher.check_needs_rehash(password_hash)


def generate_opaque_token() -> str:
    """Return a URL-safe cryptographically random token."""
    return secrets.token_urlsafe(OPAQUE_TOKEN_BYTES)


def hash_opaque_token(raw_token: str) -> str:
    """Return the SHA-256 hex digest of an opaque token for database storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AccessTokenClaims:
    user_id: int
    organization_id: int
    role: str
    jti: str


def create_access_token(
    *,
    user_id: int,
    organization_id: int,
    role: str,
    settings: Settings,
) -> str:
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "org": organization_id,
        "role": role,
        "type": ACCESS_TOKEN_TYPE,
        "jti": uuid.uuid4().hex,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> AccessTokenClaims:
    """Validate signature, expiration, and claims. Raises UnauthorizedError on any failure."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "org", "role", "type", "exp", "iat", "jti"]},
        )
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Invalid or expired access token") from exc

    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise UnauthorizedError("Invalid token type")

    try:
        user_id = int(payload["sub"])
        organization_id = int(payload["org"])
        role = str(payload["role"])
        jti = str(payload["jti"])
    except (KeyError, TypeError, ValueError) as exc:
        raise UnauthorizedError("Malformed access token claims") from exc

    return AccessTokenClaims(
        user_id=user_id,
        organization_id=organization_id,
        role=role,
        jti=jti,
    )
