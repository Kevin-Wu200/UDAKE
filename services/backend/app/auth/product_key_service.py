"""Product key generation and validation."""

from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass
from typing import Callable, Dict, Optional

BASE36_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
PRODUCT_KEY_PATTERN = re.compile(r"^[A-Z0-9]{3}(?:-[A-Z0-9]{4}){3}$")
CHECKSUM_WEIGHTS = [3, 7, 2, 9, 5, 1, 8, 4, 6]
_DIGEST_INFO_SHA256_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")


class ProductKeyValidationError(ValueError):
    """Raised when product key validation fails."""


@dataclass
class ProductKeyRecord:
    product_key: str
    status: str = "unused"
    key_type: str = "personal"
    signature: Optional[str] = None
    metadata: Optional[dict] = None


def base36_encode(value: int) -> str:
    """Encode integer to Base36 string."""
    if value < 0:
        raise ValueError("base36 only supports non-negative integers")
    if value == 0:
        return "0"
    digits = []
    remaining = value
    while remaining > 0:
        remaining, mod = divmod(remaining, 36)
        digits.append(BASE36_ALPHABET[mod])
    return "".join(reversed(digits))


def base36_decode(value: str) -> int:
    """Decode Base36 string to integer."""
    text = value.strip().upper()
    if not text:
        raise ValueError("base36 string must not be empty")
    result = 0
    for ch in text:
        idx = BASE36_ALPHABET.find(ch)
        if idx < 0:
            raise ValueError(f"invalid base36 char: {ch}")
        result = result * 36 + idx
    return result


def _base36_chars_from_digest(digest: bytes, length: int) -> str:
    encoded = base36_encode(int.from_bytes(digest, "big"))
    return encoded.zfill(length)[-length:]


def _normalize_key(product_key: str) -> str:
    return product_key.strip().upper()


def _key_raw(product_key: str) -> str:
    return product_key.replace("-", "").upper()


def _expected_checksum_char(raw_key: str) -> str:
    values = [base36_decode(ch) for ch in raw_key[:9]]
    checksum = sum(v * w for v, w in zip(values, CHECKSUM_WEIGHTS)) % 36
    return BASE36_ALPHABET[checksum]


def _expected_hash_suffix(raw_key: str) -> str:
    digest = hashlib.sha256(raw_key[:10].encode("ascii")).digest()
    return _base36_chars_from_digest(digest, 5)


def _read_length(data: bytes, offset: int) -> tuple[int, int]:
    first = data[offset]
    offset += 1
    if first < 0x80:
        return first, offset
    count = first & 0x7F
    if count <= 0 or count > 4:
        raise ProductKeyValidationError("invalid ASN.1 length")
    length = int.from_bytes(data[offset : offset + count], "big")
    return length, offset + count


def _read_tlv(data: bytes, offset: int) -> tuple[int, bytes, int]:
    if offset >= len(data):
        raise ProductKeyValidationError("invalid ASN.1 structure")
    tag = data[offset]
    length, cursor = _read_length(data, offset + 1)
    end = cursor + length
    if end > len(data):
        raise ProductKeyValidationError("invalid ASN.1 length overflow")
    return tag, data[cursor:end], end


def _parse_rsa_public_numbers(public_key_pem: str) -> tuple[int, int]:
    try:
        from cryptography.hazmat.primitives import serialization  # type: ignore
        from cryptography.hazmat.primitives.asymmetric import rsa  # type: ignore

        loaded = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
        if isinstance(loaded, rsa.RSAPublicKey):
            numbers = loaded.public_numbers()
            return numbers.n, numbers.e
    except Exception:
        pass

    body = "".join(
        line.strip()
        for line in public_key_pem.strip().splitlines()
        if "BEGIN" not in line and "END" not in line
    )
    try:
        der = base64.b64decode(body)
    except Exception as exc:
        raise ProductKeyValidationError("invalid public key PEM") from exc

    tag, content, _ = _read_tlv(der, 0)
    if tag != 0x30:
        raise ProductKeyValidationError("invalid public key sequence")

    inner_offset = 0
    first_tag, first_value, first_end = _read_tlv(content, inner_offset)
    if first_tag == 0x02:
        second_tag, second_value, _ = _read_tlv(content, first_end)
        if second_tag != 0x02:
            raise ProductKeyValidationError("invalid rsa public key")
        return int.from_bytes(first_value, "big"), int.from_bytes(second_value, "big")

    if first_tag != 0x30:
        raise ProductKeyValidationError("unsupported public key format")
    bit_tag, bit_value, _ = _read_tlv(content, first_end)
    if bit_tag != 0x03 or not bit_value:
        raise ProductKeyValidationError("invalid subjectPublicKey bitstring")
    if bit_value[0] != 0:
        raise ProductKeyValidationError("unsupported bitstring padding")

    rsa_der = bit_value[1:]
    rsa_tag, rsa_content, _ = _read_tlv(rsa_der, 0)
    if rsa_tag != 0x30:
        raise ProductKeyValidationError("invalid rsa key structure")
    n_tag, n_value, n_end = _read_tlv(rsa_content, 0)
    e_tag, e_value, _ = _read_tlv(rsa_content, n_end)
    if n_tag != 0x02 or e_tag != 0x02:
        raise ProductKeyValidationError("invalid rsa integers")
    return int.from_bytes(n_value, "big"), int.from_bytes(e_value, "big")


def verify_rsa_signature_sha256(message: bytes, signature_b64: str, public_key_pem: str) -> bool:
    """Verify RSA PKCS#1 v1.5 signature with SHA-256."""
    try:
        signature = base64.b64decode(signature_b64)
    except Exception:
        return False

    try:
        n, e = _parse_rsa_public_numbers(public_key_pem)
    except ProductKeyValidationError:
        return False

    key_size = (n.bit_length() + 7) // 8
    if len(signature) != key_size:
        return False

    em = pow(int.from_bytes(signature, "big"), e, n).to_bytes(key_size, "big")
    digest = hashlib.sha256(message).digest()
    t = _DIGEST_INFO_SHA256_PREFIX + digest
    ps_len = key_size - len(t) - 3
    if ps_len < 8:
        return False
    expected = b"\x00\x01" + (b"\xff" * ps_len) + b"\x00" + t
    return em == expected


class ProductKeyRegistry:
    """In-memory product key registry with deterministic validation algorithm."""

    def __init__(self) -> None:
        self._keys: Dict[str, ProductKeyRecord] = {}

    def register_key(self, record: ProductKeyRecord) -> None:
        self._keys[_normalize_key(record.product_key)] = record

    def get_record(self, product_key: str) -> Optional[ProductKeyRecord]:
        return self._keys.get(_normalize_key(product_key))

    def generate_key(self, seed: str, *, key_type: str = "personal") -> ProductKeyRecord:
        digest = hashlib.sha256(seed.encode("utf-8")).digest()
        body = _base36_chars_from_digest(digest, 9)
        checksum = _expected_checksum_char(body + "0")
        prefix = body + checksum
        suffix = _expected_hash_suffix(prefix + "00000")
        raw = prefix + suffix
        formatted = f"{raw[:3]}-{raw[3:7]}-{raw[7:11]}-{raw[11:15]}"
        record = ProductKeyRecord(product_key=formatted, key_type=key_type, status="unused")
        self.register_key(record)
        return record

    def validate_key_format(self, product_key: str) -> None:
        normalized = _normalize_key(product_key)
        if not PRODUCT_KEY_PATTERN.fullmatch(normalized):
            raise ProductKeyValidationError("product key format invalid")

    def validate_checksum(self, product_key: str) -> None:
        raw = _key_raw(product_key)
        expected_checksum = _expected_checksum_char(raw)
        if raw[9] != expected_checksum:
            raise ProductKeyValidationError("product key checksum mismatch")
        expected_suffix = _expected_hash_suffix(raw)
        if raw[10:] != expected_suffix:
            raise ProductKeyValidationError("product key hash tail mismatch")

    def validate_key(
        self,
        product_key: str,
        *,
        query_func: Optional[Callable[[str], Optional[ProductKeyRecord]]] = None,
        require_unused: bool = True,
        enterprise_public_key_pem: Optional[str] = None,
    ) -> ProductKeyRecord:
        self.validate_key_format(product_key)
        self.validate_checksum(product_key)

        normalized = _normalize_key(product_key)
        record = None
        if query_func:
            record = query_func(normalized)
        if record is None:
            record = self.get_record(normalized)
        if not record:
            raise ProductKeyValidationError("product key not found")
        if require_unused and record.status != "unused":
            raise ProductKeyValidationError(f"product key status invalid: {record.status}")

        if record.key_type == "enterprise":
            if not record.signature:
                raise ProductKeyValidationError("enterprise key missing signature")
            if not enterprise_public_key_pem:
                raise ProductKeyValidationError("enterprise key requires RSA public key")
            valid_signature = verify_rsa_signature_sha256(
                message=normalized.encode("ascii"),
                signature_b64=record.signature,
                public_key_pem=enterprise_public_key_pem,
            )
            if not valid_signature:
                raise ProductKeyValidationError("enterprise key signature invalid")

        return record
