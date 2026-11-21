"""Encrypted secret storage (Fernet) and inbound webhook signature verification."""

import base64
import hashlib
import hmac
import time

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings
from app.core.errors import UnauthorizedError

SIGNATURE_HEADER = "X-OpsPilot-Signature"
BEARER_PREFIX = "Bearer "


def _fernet_for_settings(settings: Settings) -> Fernet:
    if settings.integration_encryption_key:
        return Fernet(settings.integration_encryption_key.encode("utf-8"))
    # Dev/test fallback derived from jwt_secret_key; production requires explicit key.
    digest = hashlib.sha256(settings.jwt_secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plaintext: str, settings: Settings) -> str:
    return _fernet_for_settings(settings).encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str, settings: Settings) -> str:
    try:
        return _fernet_for_settings(settings).decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise UnauthorizedError("Unable to decrypt integration signing secret") from exc


def sign_webhook_payload(raw_body: bytes, secret: str, *, timestamp: int | None = None) -> str:
    """Compute ``X-OpsPilot-Signature: t=<unix_ts>,v1=<hmac_sha256_hex>``."""
    ts = timestamp if timestamp is not None else int(time.time())
    signed_content = f"{ts}.".encode() + raw_body
    sig = hmac.new(secret.encode("utf-8"), signed_content, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def _parse_signature_header(header_value: str) -> tuple[int, str]:
    parts: dict[str, str] = {}
    for chunk in header_value.split(","):
        if "=" not in chunk:
            continue
        k, v = chunk.strip().split("=", 1)
        parts[k.strip()] = v.strip()
    if "t" not in parts or "v1" not in parts or not parts["t"].isdigit():
        raise UnauthorizedError("Invalid webhook signature header")
    return int(parts["t"]), parts["v1"]


def verify_webhook_credentials(
    *,
    raw_body: bytes,
    signature_header: str | None,
    authorization_header: str | None,
    candidate_secrets: list[str],
    tolerance_seconds: int,
    now_ts: int | None = None,
) -> None:
    """Verify HMAC-SHA256+timestamp signature, or Bearer token fallback."""
    if signature_header:
        ts, provided_sig = _parse_signature_header(signature_header)
        current = now_ts if now_ts is not None else int(time.time())
        if abs(current - ts) > tolerance_seconds:
            raise UnauthorizedError("Webhook timestamp outside allowed replay window")

        signed_content = f"{ts}.".encode() + raw_body
        for secret in candidate_secrets:
            expected = hmac.new(secret.encode("utf-8"), signed_content, hashlib.sha256).hexdigest()
            if hmac.compare_digest(expected, provided_sig):
                return
        raise UnauthorizedError("Invalid webhook signature")

    if authorization_header and authorization_header.startswith(BEARER_PREFIX):
        bearer = authorization_header.removeprefix(BEARER_PREFIX).strip()
        for secret in candidate_secrets:
            if hmac.compare_digest(secret, bearer):
                return
        raise UnauthorizedError("Invalid webhook bearer token")

    raise UnauthorizedError("Missing webhook authentication credentials")


GITHUB_SIGNATURE_HEADER = "X-Hub-Signature-256"


def verify_github_webhook_signature(
    *, raw_body: bytes, signature_header: str | None, secret: str
) -> None:
    """Verify GitHub ``X-Hub-Signature-256: sha256=<hex>`` in constant time."""
    if not signature_header or not signature_header.startswith("sha256="):
        raise UnauthorizedError("Missing or invalid GitHub webhook signature")
    provided = signature_header.removeprefix("sha256=").strip()
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, provided):
        raise UnauthorizedError("Invalid GitHub webhook signature")
