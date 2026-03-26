"""Security primitives for authentication core module."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import struct
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Iterable, List, Mapping, MutableMapping, Sequence

TOKENS_MAGIC = b"TKNS"
TOKENS_VERSION = 1
_TAG_LENGTH = 16
_HEADER_STRUCT = struct.Struct(">4sBBBBBIIB")
_MIN_HEADER_SIZE = _HEADER_STRUCT.size


class TokenFileFormatError(ValueError):
    """Raised when tokens.enc blob is malformed or can not be decrypted."""


@dataclass(frozen=True)
class TokenBlobHeader:
    """Parsed metadata of tokens.enc binary blob."""

    magic: bytes
    version: int
    time_cost: int
    parallelism: int
    salt_length: int
    nonce_length: int
    memory_cost: int
    ciphertext_length: int
    tag_length: int


def _b64_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _derive_key_scrypt_fallback(
    password: str,
    salt: bytes,
    key_length: int,
    time_cost: int,
    memory_cost: int,
    parallelism: int,
) -> bytes:
    n_candidate = max(2, memory_cost // 2)
    n = 1 << (n_candidate.bit_length() - 1)
    r = 8
    p = max(1, parallelism)
    maxmem = max(memory_cost, 8_192) * 2_048
    if hasattr(hashlib, "scrypt"):
        try:
            return hashlib.scrypt(
                password.encode("utf-8"),
                salt=salt,
                n=n,
                r=r,
                p=p,
                dklen=key_length,
                maxmem=maxmem,
            )
        except (ValueError, OSError):
            pass

    iterations = max(1, time_cost) * 120_000
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations=iterations,
        dklen=key_length,
    )


def derive_argon2id_key(
    password: str,
    salt: bytes,
    *,
    key_length: int = 32,
    time_cost: int = 3,
    memory_cost: int = 65_536,
    parallelism: int = 4,
) -> bytes:
    """
    Derive symmetric key using Argon2id settings.

    The function uses argon2-cffi when available. If argon2-cffi is missing,
    it falls back to a deterministic scrypt/PBKDF2 scheme to keep runtime
    compatibility in constrained environments.
    """

    if not isinstance(salt, (bytes, bytearray)) or len(salt) < 8:
        raise ValueError("salt must be bytes and length >= 8")
    if key_length <= 0:
        raise ValueError("key_length must be positive")

    try:
        from argon2.low_level import Type, hash_secret_raw  # type: ignore

        return hash_secret_raw(
            secret=password.encode("utf-8"),
            salt=bytes(salt),
            time_cost=time_cost,
            memory_cost=memory_cost,
            parallelism=parallelism,
            hash_len=key_length,
            type=Type.ID,
        )
    except Exception:
        return _derive_key_scrypt_fallback(
            password=password,
            salt=bytes(salt),
            key_length=key_length,
            time_cost=time_cost,
            memory_cost=memory_cost,
            parallelism=parallelism,
        )


def _encrypt_aes_gcm(key: bytes, nonce: bytes, plaintext: bytes) -> tuple[bytes, bytes]:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore

        encrypted = AESGCM(key).encrypt(nonce, plaintext, None)
        return encrypted[:-_TAG_LENGTH], encrypted[-_TAG_LENGTH:]
    except Exception:
        stream = bytearray()
        counter = 0
        while len(stream) < len(plaintext):
            stream.extend(hashlib.sha256(key + nonce + counter.to_bytes(4, "big")).digest())
            counter += 1
        ciphertext = bytes(a ^ b for a, b in zip(plaintext, stream))
        tag = hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()[:_TAG_LENGTH]
        return ciphertext, tag


def _decrypt_aes_gcm(key: bytes, nonce: bytes, ciphertext: bytes, tag: bytes) -> bytes:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore

        return AESGCM(key).decrypt(nonce, ciphertext + tag, None)
    except Exception:
        expected = hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()[:_TAG_LENGTH]
        if not hmac.compare_digest(expected, tag):
            raise TokenFileFormatError("decrypt failed: authentication tag mismatch")
        stream = bytearray()
        counter = 0
        while len(stream) < len(ciphertext):
            stream.extend(hashlib.sha256(key + nonce + counter.to_bytes(4, "big")).digest())
            counter += 1
        return bytes(a ^ b for a, b in zip(ciphertext, stream))


def parse_tokens_blob_header(data: bytes) -> TokenBlobHeader:
    """Parse binary tokens blob header and validate magic/version."""
    if len(data) < _MIN_HEADER_SIZE:
        raise TokenFileFormatError("file corrupted: header is incomplete")

    (
        magic,
        version,
        time_cost,
        parallelism,
        salt_length,
        nonce_length,
        memory_cost,
        ciphertext_length,
        tag_length,
    ) = _HEADER_STRUCT.unpack_from(data, 0)

    if magic != TOKENS_MAGIC:
        raise TokenFileFormatError("invalid header: unexpected magic number")
    if version != TOKENS_VERSION:
        raise TokenFileFormatError(f"unsupported tokens version: {version}")
    if salt_length < 8 or nonce_length < 8:
        raise TokenFileFormatError("invalid header: salt/nonce length is too small")
    if tag_length != _TAG_LENGTH:
        raise TokenFileFormatError("invalid header: unsupported tag length")
    if ciphertext_length < 1:
        raise TokenFileFormatError("invalid header: ciphertext length is invalid")

    return TokenBlobHeader(
        magic=magic,
        version=version,
        time_cost=time_cost,
        parallelism=parallelism,
        salt_length=salt_length,
        nonce_length=nonce_length,
        memory_cost=memory_cost,
        ciphertext_length=ciphertext_length,
        tag_length=tag_length,
    )


def encrypt_tokens_blob(
    payload: bytes | str | Mapping[str, object],
    password: str,
    *,
    time_cost: int = 3,
    memory_cost: int = 65_536,
    parallelism: int = 4,
) -> bytes:
    """Encrypt payload to a binary tokens.enc-compatible blob."""
    if isinstance(payload, Mapping):
        plaintext = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    elif isinstance(payload, str):
        plaintext = payload.encode("utf-8")
    else:
        plaintext = bytes(payload)

    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = derive_argon2id_key(
        password,
        salt,
        key_length=32,
        time_cost=time_cost,
        memory_cost=memory_cost,
        parallelism=parallelism,
    )
    ciphertext, tag = _encrypt_aes_gcm(key, nonce, plaintext)
    header = _HEADER_STRUCT.pack(
        TOKENS_MAGIC,
        TOKENS_VERSION,
        time_cost,
        parallelism,
        len(salt),
        len(nonce),
        memory_cost,
        len(ciphertext),
        len(tag),
    )
    return header + salt + nonce + ciphertext + tag


def decrypt_tokens_blob(blob: bytes, password: str, *, decode_json: bool = False) -> bytes | MutableMapping[str, object]:
    """Decrypt binary tokens blob and return plaintext bytes (or JSON object)."""
    header = parse_tokens_blob_header(blob)
    total_size = (
        _MIN_HEADER_SIZE
        + header.salt_length
        + header.nonce_length
        + header.ciphertext_length
        + header.tag_length
    )
    if len(blob) != total_size:
        raise TokenFileFormatError("file corrupted: payload size mismatch")

    offset = _MIN_HEADER_SIZE
    salt = blob[offset : offset + header.salt_length]
    offset += header.salt_length
    nonce = blob[offset : offset + header.nonce_length]
    offset += header.nonce_length
    ciphertext = blob[offset : offset + header.ciphertext_length]
    offset += header.ciphertext_length
    tag = blob[offset : offset + header.tag_length]

    key = derive_argon2id_key(
        password,
        salt,
        key_length=32,
        time_cost=header.time_cost,
        memory_cost=header.memory_cost,
        parallelism=header.parallelism,
    )
    try:
        plaintext = _decrypt_aes_gcm(key, nonce, ciphertext, tag)
    except TokenFileFormatError:
        raise
    except Exception as exc:
        raise TokenFileFormatError("decrypt failed") from exc

    if not decode_json:
        return plaintext
    try:
        return json.loads(plaintext.decode("utf-8"))
    except Exception as exc:
        raise TokenFileFormatError("decrypt succeeded but JSON decoding failed") from exc


def hash_password(
    password: str,
    *,
    time_cost: int = 3,
    memory_cost: int = 65_536,
    parallelism: int = 4,
    hash_length: int = 32,
) -> str:
    """Hash password and return encoded text that includes salt + hash."""
    if not password:
        raise ValueError("password must not be empty")
    salt = os.urandom(16)
    digest = derive_argon2id_key(
        password,
        salt,
        key_length=hash_length,
        time_cost=time_cost,
        memory_cost=memory_cost,
        parallelism=parallelism,
    )
    return (
        "argon2id"
        f"$v=1$t={time_cost}$m={memory_cost}$p={parallelism}$l={hash_length}"
        f"${_b64_encode(salt)}${_b64_encode(digest)}"
    )


def verify_password(password: str, encoded_hash: str) -> bool:
    """Verify password by encoded hash string."""
    try:
        parts = encoded_hash.split("$")
        if len(parts) != 8 or parts[0] != "argon2id":
            return False
        params = {}
        for token in parts[2:6]:
            key, raw = token.split("=", 1)
            params[key] = int(raw)
        salt = _b64_decode(parts[6])
        expected = _b64_decode(parts[7])
    except Exception:
        return False

    actual = derive_argon2id_key(
        password,
        salt,
        key_length=params.get("l", len(expected)),
        time_cost=params.get("t", 3),
        memory_cost=params.get("m", 65_536),
        parallelism=params.get("p", 4),
    )
    return hmac.compare_digest(actual, expected)


def hash_passwords_parallel(
    passwords: Sequence[str] | Iterable[str],
    *,
    max_workers: int | None = None,
    time_cost: int = 3,
    memory_cost: int = 65_536,
    parallelism: int = 4,
    hash_length: int = 32,
) -> List[str]:
    """Hash multiple passwords concurrently in thread pool."""
    password_list = list(passwords)
    if not password_list:
        return []

    def _task(item: str) -> str:
        return hash_password(
            item,
            time_cost=time_cost,
            memory_cost=memory_cost,
            parallelism=parallelism,
            hash_length=hash_length,
        )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(_task, password_list))
