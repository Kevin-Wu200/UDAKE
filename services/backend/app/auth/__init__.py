"""Core authentication module for UDAKE backend."""

from .auth_service import AuthService, get_auth_service, reset_auth_service
from .cache import AuthCacheManager, CacheUnavailableError
from .jwt_service import JWTManager, JWTValidationError
from .product_key_service import ProductKeyRegistry, ProductKeyValidationError
from .security import (
    TokenFileFormatError,
    decrypt_tokens_blob,
    derive_argon2id_key,
    encrypt_tokens_blob,
    hash_password,
    hash_passwords_parallel,
    parse_tokens_blob_header,
    verify_password,
)
from .verification import EmailVerificationService, VerificationCodeError

__all__ = [
    "AuthService",
    "AuthCacheManager",
    "CacheUnavailableError",
    "EmailVerificationService",
    "JWTManager",
    "JWTValidationError",
    "ProductKeyRegistry",
    "ProductKeyValidationError",
    "TokenFileFormatError",
    "VerificationCodeError",
    "decrypt_tokens_blob",
    "derive_argon2id_key",
    "encrypt_tokens_blob",
    "get_auth_service",
    "hash_password",
    "hash_passwords_parallel",
    "parse_tokens_blob_header",
    "reset_auth_service",
    "verify_password",
]
