"""Core authentication module for UDAKE backend."""

from .auth_service import AuthService, get_auth_service, reset_auth_service
from .cache import AuthCacheManager, CacheUnavailableError
from .csrf import CSRFManager, CSRFValidationError
from .email_service import EmailDeliveryError, InvalidEmailAddressError, SMTPEmailService
from .email_templates import EmailTemplateManager
from .input_sanitizer import ensure_safe_text, sanitize_payload, sanitize_text
from .ip_control import IPAccessController, IPCheckResult
from .jwt_service import JWTManager, JWTValidationError
from .product_key_service import ProductKeyRegistry, ProductKeyValidationError
from .rate_limiter import AuthRateLimiter, RateLimitExceededError, rate_limit, reset_auth_rate_limiter
from .security import (
    SensitiveDataCipher,
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
    "CSRFManager",
    "CSRFValidationError",
    "EmailDeliveryError",
    "EmailVerificationService",
    "EmailTemplateManager",
    "IPAccessController",
    "IPCheckResult",
    "AuthRateLimiter",
    "InvalidEmailAddressError",
    "JWTManager",
    "JWTValidationError",
    "ProductKeyRegistry",
    "ProductKeyValidationError",
    "RateLimitExceededError",
    "SMTPEmailService",
    "SensitiveDataCipher",
    "TokenFileFormatError",
    "VerificationCodeError",
    "decrypt_tokens_blob",
    "derive_argon2id_key",
    "encrypt_tokens_blob",
    "get_auth_service",
    "hash_password",
    "hash_passwords_parallel",
    "ensure_safe_text",
    "sanitize_payload",
    "sanitize_text",
    "parse_tokens_blob_header",
    "rate_limit",
    "reset_auth_rate_limiter",
    "reset_auth_service",
    "verify_password",
]
