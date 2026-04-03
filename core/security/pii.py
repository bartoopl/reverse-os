"""
PII Vault encryption/decryption layer.
All access to customer PII must go through this module.
Never expose raw PII to analytics, logs, or external systems.
"""
import base64
import hashlib
import json
import re

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from core.config import settings


def _get_key() -> bytes:
    raw = settings.PII_ENCRYPTION_KEY.get_secret_value()
    return base64.b64decode(raw)


def encrypt(plaintext: str) -> bytes:
    """AES-256-GCM encrypt a string. Returns nonce + ciphertext."""
    import os
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return nonce + ct


def decrypt(ciphertext: bytes) -> str:
    """AES-256-GCM decrypt. Raises InvalidTag if tampered."""
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce, ct = ciphertext[:12], ciphertext[12:]
    return aesgcm.decrypt(nonce, ct, None).decode()


def mask_email(email: str) -> str:
    """jan.kowalski@gmail.com -> j***@g***.com  (for logs/analytics)"""
    if "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    domain_parts = domain.split(".")
    masked_local = local[0] + "***"
    masked_domain = domain_parts[0][0] + "***"
    tld = domain_parts[-1] if len(domain_parts) > 1 else ""
    return f"{masked_local}@{masked_domain}.{tld}"


def mask_name(name: str) -> str:
    """Jan Kowalski -> J*** K***"""
    parts = name.split()
    return " ".join(p[0] + "***" for p in parts if p)


def anonymize_payload(data: dict) -> dict:
    """
    Recursively mask PII fields before sending to logs or analytics.
    Fields detected by key name pattern.
    """
    PII_FIELDS = re.compile(
        r"(email|phone|name|address|street|postal|zip|city|surname)", re.IGNORECASE
    )
    result = {}
    for k, v in data.items():
        if PII_FIELDS.search(k):
            if isinstance(v, str) and "@" in v:
                result[k] = mask_email(v)
            elif isinstance(v, str):
                result[k] = v[:1] + "***" if v else "***"
            else:
                result[k] = "***"
        elif isinstance(v, dict):
            result[k] = anonymize_payload(v)
        else:
            result[k] = v
    return result
