import sys
content = open('services/backend/app/auth/auth_service.py').read()
old = """def get_auth_service() -> AuthService:
    global _AUTH_SERVICE
    if _AUTH_SERVICE is None:
        with _AUTH_SERVICE_LOCK:
            if _AUTH_SERVICE is None:
                from app.config import settings

                cache = AuthCacheManager(redis_url=settings.REDIS_URL, pool_size=10, strict_redis=False)
                jwt_manager = JWTManager(secret_key=_resolve_jwt_secret(), cache_manager=cache)
                service = AuthService(cache=cache, jwt_manager=jwt_manager)
                print("DEBUG: AuthService init")
                service.load_users_from_db()

                bootstrap_seed = os.getenv("AUTH_BOOTSTRAP_PRODUCT_KEY", "UDAKE-DEFAULT-PRODUCT-KEY")
                bootstrap_record = service.product_keys.generate_key(bootstrap_seed)
                service._bootstrap_product_key_alias = bootstrap_seed.strip().upper()
                service._bootstrap_product_key = bootstrap_record.product_key
                cache.set_with_jitter(
                    "auth:warmup:product_keys",
                    {"keys": [bootstrap_record.product_key], "count": 1},
                    ttl=1800,
                    jitter_ratio=0.2,
                )
                cache.set_with_jitter(
                    "auth:warmup:user_summary",
                    {"total_users": 0, "cached_at": int(time.time())},
                    ttl=1800,
                    jitter_ratio=0.2,
                )
                _AUTH_SERVICE = service
    return _AUTH_SERVICE"""

new = """def get_auth_service() -> AuthService:
    global _AUTH_SERVICE
    if _AUTH_SERVICE is None:
        with _AUTH_SERVICE_LOCK:
            if _AUTH_SERVICE is None:
                from app.config import settings

                cache = AuthCacheManager(redis_url=settings.REDIS_URL, pool_size=10, strict_redis=False)
                jwt_manager = JWTManager(secret_key=_resolve_jwt_secret(), cache_manager=cache)
                service = AuthService(cache=cache, jwt_manager=jwt_manager)
                service.load_users_from_db()

                bootstrap_seed = os.getenv("AUTH_BOOTSTRAP_PRODUCT_KEY", "UDAKE-DEFAULT-PRODUCT-KEY")
                bootstrap_record = service.product_keys.generate_key(bootstrap_seed)
                service._bootstrap_product_key_alias = bootstrap_seed.strip().upper()
                service._bootstrap_product_key = bootstrap_record.product_key
                cache.set_with_jitter(
                    "auth:warmup:product_keys",
                    {"keys": [bootstrap_record.product_key], "count": 1},
                    ttl=1800,
                    jitter_ratio=0.2,
                )
                cache.set_with_jitter(
                    "auth:warmup:user_summary",
                    {"total_users": 0, "cached_at": int(time.time())},
                    ttl=1800,
                    jitter_ratio=0.2,
                )
                _AUTH_SERVICE = service
    if _AUTH_SERVICE and not _AUTH_SERVICE._users_by_email:
        _AUTH_SERVICE.load_users_from_db()
    return _AUTH_SERVICE"""

with open('services/backend/app/auth/auth_service.py', 'w') as f:
    f.write(content.replace(old, new))
