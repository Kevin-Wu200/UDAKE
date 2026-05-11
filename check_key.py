import hashlib

BASE36_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
CHECKSUM_WEIGHTS = [3, 7, 2, 9, 5, 1, 8, 4, 6]

def base36_encode(value: int) -> str:
    if value < 0: return "0"
    if value == 0: return "0"
    digits = []
    remaining = value
    while remaining > 0:
        remaining, mod = divmod(remaining, 36)
        digits.append(BASE36_ALPHABET[mod])
    return "".join(reversed(digits))

def base36_decode(value: str) -> int:
    text = value.strip().upper()
    result = 0
    for ch in text:
        idx = BASE36_ALPHABET.find(ch)
        result = result * 36 + idx
    return result

def _base36_chars_from_digest(digest: bytes, length: int) -> str:
    encoded = base36_encode(int.from_bytes(digest, "big"))
    return encoded.zfill(length)[-length:]

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

key = "MUU-290U-18DP-NU6B"
raw = key.replace("-", "").upper()
body = raw[:9]
checksum = raw[9]
suffix = raw[10:]

print(f"Key: {key}")
print(f"Raw: {raw}")
print(f"Body: {body}, Checksum: {checksum}, Suffix: {suffix}")

# V2 check
expected_checksum_v2 = _expected_checksum_char_v2(body + "0")
expected_suffix_v2 = _expected_hash_suffix_v2((body + expected_checksum_v2) + "00000")
print(f"V2 Expected: Checksum={expected_checksum_v2}, Suffix={expected_suffix_v2}")

# Legacy check
expected_checksum_legacy = _expected_checksum_char_legacy(raw)
expected_suffix_legacy = _expected_hash_suffix_legacy(body + expected_checksum_legacy)
print(f"Legacy Expected: Checksum={expected_checksum_legacy}, Suffix={expected_suffix_legacy}")

if checksum == expected_checksum_v2 and suffix == expected_suffix_v2:
    print("MATCH V2")
elif checksum == expected_checksum_legacy and suffix == expected_suffix_legacy:
    print("MATCH LEGACY")
else:
    print("NO MATCH")
