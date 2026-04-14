"""Product key generation and validation."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

try:
    from pypinyin import lazy_pinyin
except Exception:  # pragma: no cover - optional dependency fallback
    lazy_pinyin = None  # type: ignore[assignment]

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
    key_type: str = "personal_standard"
    key_sub_type: str = "standard"
    total_quota: int = 100
    used_count: int = 0
    user_id: Optional[int] = None
    company_id: Optional[int] = None
    generation_seed: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    signature: Optional[str] = None


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


def _expected_checksum_char_legacy(raw_key: str) -> str:
    values = [base36_decode(ch) for ch in raw_key[:9]]
    checksum = sum(v * w for v, w in zip(values, CHECKSUM_WEIGHTS)) % 36
    return BASE36_ALPHABET[checksum]


def _expected_hash_suffix_legacy(raw_key: str) -> str:
    digest = hashlib.sha256(raw_key[:10].encode("ascii")).digest()
    return _base36_chars_from_digest(digest, 5)


def _expected_checksum_char_v2(data: str) -> str:
    digest = hashlib.sha256(data.encode("ascii")).digest()
    return BASE36_ALPHABET[int.from_bytes(digest, "big") % 36]


def _expected_hash_suffix_v2(data: str) -> str:
    digest = hashlib.sha256(data.encode("ascii")).digest()
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
    """In-memory product key registry with enterprise/personal generation support."""

    def __init__(self) -> None:
        self._keys: Dict[str, ProductKeyRecord] = {}
        self._counter = 0

    def register_key(self, record: ProductKeyRecord) -> None:
        self._keys[_normalize_key(record.product_key)] = record

    def get_record(self, product_key: str) -> Optional[ProductKeyRecord]:
        return self._keys.get(_normalize_key(product_key))

    def _next_counter(self) -> int:
        self._counter += 1
        return self._counter

    def _build_key_from_seed(self, seed: str) -> str:
        digest = hashlib.sha256(seed.encode("utf-8")).digest()
        body = _base36_chars_from_digest(digest, 9)
        checksum = _expected_checksum_char_v2(body + "0")
        prefix = body + checksum
        suffix = _expected_hash_suffix_v2(prefix + "00000")
        raw = prefix + suffix
        return f"{raw[:3]}-{raw[3:7]}-{raw[7:11]}-{raw[11:15]}"

    @staticmethod
    def _key_sub_type_from_type(key_type: str) -> str:
        return "trial" if str(key_type).endswith("_trial") else "standard"

    @staticmethod
    def _get_quota_for_type(key_type: str) -> int:
        quota_map = {
            "personal_trial": 10,
            "personal_standard": 100,
            "enterprise_trial": 500,
            "enterprise_standard": 1000,
        }
        return quota_map.get(key_type, 1)

    @staticmethod
    def _company_initials(company_name: str) -> str:
        text = str(company_name or "").strip()
        if not text:
            return "".join(secrets.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(3))

        initials = ""
        if lazy_pinyin:
            pinyin_items = lazy_pinyin(text)
            initials = "".join(item[0].upper() for item in pinyin_items if item)
        if not initials:
            initials = "".join(ch.upper() for ch in text if ch.isalpha() and ch.isascii())

        if len(initials) < 3:
            while len(initials) < 3:
                initials += secrets.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
            return initials
        if len(initials) > 3:
            return "".join(secrets.choice(initials) for _ in range(3))
        return initials

    def generate_enterprise_key(
        self,
        *,
        company_name: str,
        company_id: int,
        key_type: str,
    ) -> tuple[str, str]:
        company_prefix = self._company_initials(company_name)
        random_seed = secrets.token_hex(16)
        timestamp_ms = int(time.time() * 1000)
        counter = self._next_counter()
        generation_seed = (
            f"enterprise:{company_prefix}:{company_id}:{key_type}:{timestamp_ms}:{counter}:{random_seed}"
        )
        return self._build_key_from_seed(generation_seed), generation_seed

    def generate_personal_key(
        self,
        *,
        user_id: int,
        key_type: str,
    ) -> tuple[str, str]:
        random_seed = secrets.token_hex(24)
        timestamp_ms = int(time.time() * 1000)
        counter = self._next_counter()
        generation_seed = f"personal:{user_id}:{key_type}:{timestamp_ms}:{counter}:{random_seed}"
        return self._build_key_from_seed(generation_seed), generation_seed

    def generate_key(
        self,
        seed: Optional[str] = None,
        *,
        key_type: str = "personal_standard",
        user_id: Optional[int] = None,
        company_id: Optional[int] = None,
        company_name: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> ProductKeyRecord:
        key_metadata: dict[str, Any] = dict(metadata or {})
        if seed is not None:
            generation_seed = str(seed)
            product_key = self._build_key_from_seed(generation_seed)
            variant = "legacy"
        elif str(key_type).startswith("enterprise_"):
            if not company_id or not company_name:
                raise ValueError("企业密钥需要提供 company_id 和 company_name")
            product_key, generation_seed = self.generate_enterprise_key(
                company_name=company_name,
                company_id=company_id,
                key_type=key_type,
            )
            variant = "enterprise"
            key_metadata.setdefault("enterprise_name", company_name)
        else:
            if not user_id:
                raise ValueError("个人密钥需要提供 user_id")
            product_key, generation_seed = self.generate_personal_key(user_id=user_id, key_type=key_type)
            variant = "personal"

        key_metadata.setdefault("key_variant", variant)
        key_metadata.setdefault("generation_seed", generation_seed)

        record = ProductKeyRecord(
            product_key=product_key.upper(),
            key_type=key_type,
            key_sub_type=self._key_sub_type_from_type(key_type),
            status="unused",
            total_quota=self._get_quota_for_type(key_type),
            used_count=0,
            user_id=user_id,
            company_id=company_id,
            generation_seed=generation_seed,
            metadata=key_metadata,
        )
        self.register_key(record)
        return record

    def generate_keys(
        self,
        *,
        key_type: str,
        count: int,
        user_id: Optional[int] = None,
        company_id: Optional[int] = None,
        company_name: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        db: Optional[Any] = None,
        created_by: Optional[int] = None,
    ) -> list[Any]:
        if count < 1 or count > 1000:
            raise ValueError("生成数量必须在 1-1000 之间")

        created: list[Any] = []
        model_cls: Optional[type[Any]] = None
        if db is not None:
            from app.auth_db.models import ProductKey as ProductKeyModel

            model_cls = ProductKeyModel

        for index in range(count):
            item_metadata = dict(metadata or {})
            item_metadata["batch_index"] = index + 1
            item_metadata["batch_size"] = count
            record = self.generate_key(
                key_type=key_type,
                user_id=user_id,
                company_id=company_id,
                company_name=company_name,
                metadata=item_metadata,
            )

            if db is None or model_cls is None:
                created.append(record)
                continue

            db_item = model_cls(
                product_key=record.product_key,
                key_type=record.key_type,
                key_sub_type=record.key_sub_type,
                status=record.status,
                total_quota=record.total_quota,
                used_count=record.used_count,
                user_id=record.user_id or user_id or 0,
                company_id=record.company_id,
                key_metadata=json.dumps(record.metadata, ensure_ascii=False),
                generation_seed=record.generation_seed,
            )
            if hasattr(db_item, "created_by") and created_by is not None:
                setattr(db_item, "created_by", created_by)
            if hasattr(db_item, "created_by_id") and created_by is not None:
                setattr(db_item, "created_by_id", created_by)
            db.add(db_item)
            created.append(db_item)

        if db is not None:
            db.commit()
            for item in created:
                db.refresh(item)

        return created

    def validate_key_format(self, product_key: str) -> None:
        normalized = _normalize_key(product_key)
        if not PRODUCT_KEY_PATTERN.fullmatch(normalized):
            raise ProductKeyValidationError("product key format invalid")

    def validate_checksum(self, product_key: str) -> None:
        raw = _key_raw(product_key)
        if len(raw) != 15:
            raise ProductKeyValidationError("product key length invalid")

        body = raw[:9]
        checksum = raw[9]
        suffix = raw[10:]

        expected_checksum_v2 = _expected_checksum_char_v2(body + "0")
        if checksum == expected_checksum_v2:
            expected_suffix_v2 = _expected_hash_suffix_v2((body + checksum) + "00000")
            if suffix == expected_suffix_v2:
                return

        expected_checksum_legacy = _expected_checksum_char_legacy(raw)
        if checksum != expected_checksum_legacy:
            raise ProductKeyValidationError("product key checksum mismatch")
        expected_suffix_legacy = _expected_hash_suffix_legacy(raw)
        if suffix != expected_suffix_legacy:
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

        if str(record.key_type).startswith("enterprise"):
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
