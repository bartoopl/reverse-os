"""PII vault encryption and masking tests."""
import os
import base64
import pytest

# Inject test key before importing the module
os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-32-chars-minimum!!")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("PII_ENCRYPTION_KEY", base64.b64encode(os.urandom(32)).decode())

from core.security.pii import decrypt, encrypt, mask_email, mask_name, anonymize_payload


def test_encrypt_decrypt_roundtrip():
    plaintext = "jan.kowalski@gmail.com"
    ciphertext = encrypt(plaintext)
    assert isinstance(ciphertext, bytes)
    assert decrypt(ciphertext) == plaintext


def test_encrypt_produces_different_ciphertext_each_time():
    """Each encryption uses a random nonce — same plaintext != same ciphertext."""
    ct1 = encrypt("test@example.com")
    ct2 = encrypt("test@example.com")
    assert ct1 != ct2  # Different nonces


def test_tampered_ciphertext_raises():
    from cryptography.exceptions import InvalidTag
    ct = bytearray(encrypt("secret"))
    ct[-1] ^= 0xFF  # Flip a bit
    with pytest.raises(InvalidTag):
        decrypt(bytes(ct))


@pytest.mark.parametrize("email,expected", [
    ("jan.kowalski@gmail.com", "j***@g***.com"),
    ("a@b.pl", "a***@b***.pl"),
])
def test_mask_email(email, expected):
    assert mask_email(email) == expected


def test_mask_name():
    assert mask_name("Jan Kowalski") == "J*** K***"


def test_anonymize_payload():
    data = {"order_id": "123", "email": "test@example.com", "total": 99.0, "name": "Jan"}
    result = anonymize_payload(data)
    assert result["order_id"] == "123"
    assert result["total"] == 99.0
    assert "@" not in result["email"] or "***" in result["email"]
    assert "***" in result["name"]
