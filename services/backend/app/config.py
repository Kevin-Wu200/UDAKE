"""
配置文件
支持多环境配置：development（开发）、testing（测试）、production（生产）
"""
import json
import os
from pathlib import Path
from typing import List, Literal, Optional, Set, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR_PATH = Path(__file__).parent.parent
PROJECT_ROOT_PATH = BASE_DIR_PATH.parent.parent
ENV_DIR_PATH = PROJECT_ROOT_PATH / "configs" / "env"


def _parse_json_or_csv_list(value: Union[str, List[str], None], default: Optional[List[str]] = None) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return list(default or [])
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass
        return [item.strip() for item in text.split(",") if item.strip()]
    return list(default or [])


def _default_frontend_origin() -> str:
    frontend_url = os.getenv("FRONTEND_URL")
    if frontend_url:
        return frontend_url.rstrip("/")
    ip_config = os.getenv("IPCONFIG", "localhost")
    frontend_port = os.getenv("FRONTEND_PORT", "5173")
    return f"http://{ip_config}:{frontend_port}"


def _default_cors_origins() -> List[str]:
    origins = [
        _default_frontend_origin(),
        "http://172.20.10.2:6060",
        "http://localhost:3000",
        "https://localhost",
        "http://localhost",
        "capacitor://localhost",
        "ionic://localhost"
    ]
    deduped: List[str] = []
    for origin in origins:
        normalized = origin.strip()
        if normalized and normalized not in deduped:
            deduped.append(normalized)
    return deduped


class Settings(BaseSettings):
    BASE_DIR: Path = BASE_DIR_PATH
    PROJECT_ROOT: Path = PROJECT_ROOT_PATH
    ENV_DIR: Path = ENV_DIR_PATH

    model_config = SettingsConfigDict(
        env_file=str(ENV_DIR_PATH / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True
    )

    # 环境配置
    ENVIRONMENT: Literal["development", "testing", "production"] = "development"

    # 应用配置
    APP_NAME: str = "智能不确定性驱动空间决策平台"
    VERSION: str = "1.0.0"
    DEBUG: bool = True

    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS配置
    BACKEND_CORS_ORIGINS: Union[str, List[str]] = json.dumps(_default_cors_origins(), ensure_ascii=False)

    # 文件上传配置
    MAX_FILE_SIZE_MB: int = 100

    # 文件路径配置
    RESULTS_DIR: Path = BASE_DIR / "app" / "结果文件"
    DATA_DIR: Path = PROJECT_ROOT / "data" / "samples"
    ANDROID_APK_DIR: Path = PROJECT_ROOT / "android" / "app" / "build" / "outputs" / "apk" / "release"
    WINDOWS_EXE_DIR: Path = PROJECT_ROOT / "release"
    MACOS_DMG_DIR: Path = PROJECT_ROOT / "release"

    # 任务配置
    MAX_CONCURRENT_TASKS: int = 5
    TASK_TIMEOUT: int = 3600

    # 克里金配置
    DEFAULT_VARIOGRAM_MODEL: str = "spherical"
    GRID_RESOLUTION: int = 100

    # GeoScene配置
    GEOSCENE_AUTH_MODE: Literal["apikey", "enterprise"] = "apikey"
    GEOSCENE_API_KEY: str = ""
    GEOSCENE_USERNAME: str = ""
    GEOSCENE_PASSWORD: str = ""
    GEOSCENE_PORTAL_URL: str = "https://gis:7443/geoscene/"
    GEOSCENE_ENV: str = "development"
    GEOSCENE_DEFAULT_BASEMAP: str = "streets-vector"
    GEOSCENE_DEFAULT_CENTER: Union[str, List[float]] = "[139.767125,35.681236]"
    GEOSCENE_DEFAULT_ZOOM: int = 10
    GEOSCENE_TOKEN_URL: str = ""

    # 高德地图配置（从环境变量读取）
    AMAP_API_KEY: str = Field(default="", description="高德地图API密钥")
    AMAP_SECURITY_CODE: str = Field(default="", description="高德地图安全密钥")

    # 天地图配置
    TIANDITU_API_KEY: str = "YOUR_TIANDITU_API_KEY_HERE"
    TIANDITU_TOKEN: Optional[str] = None

    # AI扩展模块配置
    AI_MODEL_PATH: Optional[str] = None
    AI_CACHE_ENABLED: bool = True
    AI_MAX_BATCH_SIZE: int = 100

    # 数据库配置（可选）
    DATABASE_URL: Optional[str] = None
    AUTH_DATABASE_URL: Optional[str] = None
    AUTH_DB_POOL_SIZE: int = 10
    AUTH_DB_MAX_OVERFLOW: int = 20
    AUTH_DB_POOL_TIMEOUT: int = 30
    AUTH_DB_POOL_RECYCLE: int = 1800
    AUTH_DB_PRE_PING: bool = True
    AUTH_DB_REQUIRE_SSL: bool = True
    AUTH_DB_SSLMODE: str = "require"
    AUTH_DB_SSLCERT: Optional[str] = None
    AUTH_DB_SSLKEY: Optional[str] = None
    AUTH_DB_SSLROOTCERT: Optional[str] = None
    AUTH_DB_LOG_SLOW_QUERY_MS: int = 100
    AUTH_DB_SLOW_QUERY_ENABLED: bool = True
    AUTH_DB_READ_REPLICA_URLS: Union[str, List[str]] = "[]"
    AUTH_DB_RW_SPLIT_ENABLED: bool = False
    AUTH_DB_QUERY_CACHE_TTL_SECONDS: float = 2.0
    AUTH_DB_QUERY_CACHE_MAX_ENTRIES: int = 2048
    AUTH_DB_REPLICA_LAG_WARN_SECONDS: int = 5
    REDIS_URL: Optional[str] = None
    REDIS_ENABLED: bool = False
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    WORKFLOW_REDIS_POOL_SIZE: int = 20
    WORKFLOW_REDIS_TIMEOUT_SECONDS: int = 5
    WORKFLOW_REDIS_RETRY_TIMES: int = 3
    WORKFLOW_REDIS_STRICT: bool = False
    WORKFLOW_REDIS_CLUSTER_ENABLED: bool = False
    WORKFLOW_REDIS_CLUSTER_NODES: Union[str, List[str]] = "[]"
    CACHE_MAX_SIZE: int = 1000
    CACHE_MIN_SIZE: Optional[int] = None
    CACHE_MAX_SIZE_LIMIT: Optional[int] = None
    CACHE_SHARD_COUNT: int = 1
    CACHE_EVICTION_POLICY: Literal["lru", "lfu", "adaptive"] = "adaptive"
    CACHE_COMPRESSION_ENABLED: bool = True
    CACHE_COMPRESSION_THRESHOLD: int = 2048
    CACHE_AUTO_TUNE_ENABLED: bool = True
    CACHE_TUNE_REQUEST_INTERVAL: int = 200
    EXPLAIN_CELERY_ENABLED: bool = False
    EXPLAIN_CELERY_TASK_ALWAYS_EAGER: bool = True
    EXPLAIN_CELERY_BROKER_URL: Optional[str] = None
    EXPLAIN_CELERY_BACKEND_URL: Optional[str] = None
    EXPLAIN_TASK_TIMEOUT_SECONDS: int = 900
    EXPLAIN_TASK_TTL_SECONDS: int = 1800
    EXPLAIN_RESULT_TTL_SECONDS: int = 3600
    EXPLAIN_MAX_CONCURRENT_TASKS: int = 4
    EXPLAIN_MAX_BATCH_SIZE: int = 256
    EXPLAIN_DEFAULT_PRIORITY: int = 5
    EXPLAIN_RESULT_COMPRESSION_THRESHOLD: int = 4096
    EXPLAIN_RATE_LIMIT_PER_MINUTE: int = 30
    EXPLAIN_REQUIRE_AUTH: bool = False
    EXPLAIN_API_TOKENS: Union[str, List[str]] = "[]"
    EXPLAIN_ALLOWED_CREATORS: Union[str, List[str]] = "[]"

    # SMTP/邮件通知配置
    SMTP_HOST: str = "smtp.qq.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_USE_SSL: bool = False
    SMTP_TIMEOUT_SECONDS: int = 15
    SMTP_POOL_SIZE: int = 4
    WORKFLOW_EMAIL_WORKERS: int = 2
    WORKFLOW_EMAIL_USER_LIMIT_PER_HOUR: int = 10
    WORKFLOW_EMAIL_EVENT_LIMIT_PER_HOUR: int = 30
    WORKFLOW_EMAIL_DEDUP_SECONDS: int = 300
    WORKFLOW_EMAIL_RETRY_BACKOFF_SECONDS: str = "60,300,900"
    AUTH_SUPER_ADMIN_EMAILS: str = ""

    # 企业管理员密钥生命周期调度配置
    KEY_EXPIRY_SCHEDULER_ENABLED: bool = True
    KEY_EXPIRY_SCHEDULER_POLL_SECONDS: int = 20
    KEY_EXPIRY_SCHEDULER_EXPIRE_TIME: str = "00:10"
    KEY_EXPIRY_SCHEDULER_REMINDER_TIME: str = "00:20"
    KEY_EXPIRY_SCHEDULER_HISTORY_LIMIT: int = 200
    KEY_EXPIRY_REMINDER_RETRY_TIMES: int = 3
    KEY_EXPIRY_REMINDER_RETRY_INTERVAL_SECONDS: int = 60

    # 认证安全策略
    AUTH_ENCRYPTION_KEY: Optional[str] = None
    FEEDBACK_ENCRYPTION_KEY: Optional[str] = None
    FEEDBACK_HMAC_KEY: Optional[str] = None
    FEEDBACK_ACTIVE_KEY_ID: str = "k1"
    FEEDBACK_FALLBACK_KEYS: Union[str, List[str]] = "[]"
    FEEDBACK_MASK_FIELDS: Union[str, List[str]] = json.dumps(
        ["password", "token", "api_key", "authorization", "contact", "phone", "email"],
        ensure_ascii=False
    )
    AUTH_IP_WHITELIST: str = ""
    AUTH_IP_BLACKLIST: str = ""
    AUTH_IP_AUTO_BAN_THRESHOLD: int = 10
    AUTH_IP_AUTO_BAN_WINDOW_SECONDS: int = 3600
    AUTH_IP_AUTO_BAN_SECONDS: int = 1800
    AUTH_ACCOUNT_LOCK_5_FAIL_SECONDS: int = 1800
    AUTH_ACCOUNT_LOCK_10_FAIL_SECONDS: int = 86400
    AUTH_XSS_MAX_INPUT_LEN: int = 2048
    AUTH_CSRF_ENABLED: bool = True
    AUTH_CSRF_PROTECT_ALL: bool = False
    AUTH_CSRF_COOKIE_NAME: str = "csrf_token"
    AUTH_CSRF_HEADER_NAME: str = "x-csrf-token"
    AUTH_CSRF_COOKIE_SAMESITE: Literal["strict", "lax", "none"] = "strict"
    AUTH_CSRF_COOKIE_SECURE: bool = False
    AUTH_SECURITY_HEADERS_ENABLED: bool = True
    AUTH_CSP_POLICY: str = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    )
    PRODUCT_KEY_VALIDATE_IP_LIMIT_PER_MINUTE: int = 10
    PRODUCT_KEY_VALIDATE_KEY_LIMIT_PER_HOUR: int = 20
    PRODUCT_KEY_VALIDATE_USER_LIMIT_PER_HOUR: int = 30
    PRODUCT_KEY_VALIDATE_CACHE_ENABLED: bool = True
    PRODUCT_KEY_VALIDATE_CACHE_TTL_SECONDS: int = 300
    PRODUCT_KEY_VALIDATE_ENABLE_IP_REPUTATION: bool = True
    PRODUCT_KEY_VALIDATE_ENABLE_AUDIT_LOG: bool = True

    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FILE: Optional[str] = None

    @field_validator('BACKEND_CORS_ORIGINS', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return _default_cors_origins()
        return v

    @field_validator('GEOSCENE_DEFAULT_CENTER', mode='before')
    @classmethod
    def parse_center(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [139.767125, 35.681236]
        return v

    @field_validator('GEOSCENE_API_KEY', mode='before')
    @classmethod
    def parse_geoscene_api_key(cls, v):
        if v is None:
            return ""
        return str(v).strip()

    @field_validator(
        'FEEDBACK_FALLBACK_KEYS',
        'FEEDBACK_MASK_FIELDS',
        'WORKFLOW_REDIS_CLUSTER_NODES',
        'AUTH_DB_READ_REPLICA_URLS',
        'EXPLAIN_API_TOKENS',
        'EXPLAIN_ALLOWED_CREATORS',
        mode='before'
    )
    @classmethod
    def parse_feedback_lists(cls, v):
        return _parse_json_or_csv_list(v)

    @field_validator(
        'MAX_CONCURRENT_TASKS',
        'TASK_TIMEOUT',
        'GRID_RESOLUTION',
        'MAX_FILE_SIZE_MB',
        'AI_MAX_BATCH_SIZE',
        'AUTH_DB_POOL_SIZE',
        'AUTH_DB_MAX_OVERFLOW',
        'AUTH_DB_POOL_TIMEOUT',
        'AUTH_DB_POOL_RECYCLE',
        'AUTH_DB_LOG_SLOW_QUERY_MS',
        'AUTH_DB_REPLICA_LAG_WARN_SECONDS',
        'REDIS_PORT',
        'WORKFLOW_REDIS_POOL_SIZE',
        'WORKFLOW_REDIS_TIMEOUT_SECONDS',
        'WORKFLOW_REDIS_RETRY_TIMES',
        'KEY_EXPIRY_SCHEDULER_POLL_SECONDS',
        'KEY_EXPIRY_SCHEDULER_HISTORY_LIMIT',
        'KEY_EXPIRY_REMINDER_RETRY_TIMES',
        'KEY_EXPIRY_REMINDER_RETRY_INTERVAL_SECONDS',
        'CACHE_MAX_SIZE',
        'CACHE_SHARD_COUNT',
        'CACHE_COMPRESSION_THRESHOLD',
        'CACHE_TUNE_REQUEST_INTERVAL',
        'EXPLAIN_TASK_TIMEOUT_SECONDS',
        'EXPLAIN_TASK_TTL_SECONDS',
        'EXPLAIN_RESULT_TTL_SECONDS',
        'EXPLAIN_MAX_CONCURRENT_TASKS',
        'EXPLAIN_MAX_BATCH_SIZE',
        'EXPLAIN_RESULT_COMPRESSION_THRESHOLD',
        'EXPLAIN_RATE_LIMIT_PER_MINUTE',
        'AUTH_IP_AUTO_BAN_THRESHOLD',
        'AUTH_IP_AUTO_BAN_WINDOW_SECONDS',
        'AUTH_IP_AUTO_BAN_SECONDS',
        'AUTH_ACCOUNT_LOCK_5_FAIL_SECONDS',
        'AUTH_ACCOUNT_LOCK_10_FAIL_SECONDS',
        'AUTH_XSS_MAX_INPUT_LEN',
    )
    @classmethod
    def validate_positive_int(cls, v):
        if v <= 0:
            raise ValueError(f'{v} must be positive')
        return v

    @field_validator('EXPLAIN_DEFAULT_PRIORITY')
    @classmethod
    def validate_explain_priority(cls, v):
        iv = int(v)
        if iv < 0 or iv > 9:
            raise ValueError('EXPLAIN_DEFAULT_PRIORITY must be between 0 and 9')
        return iv

    @field_validator('AUTH_DB_QUERY_CACHE_TTL_SECONDS', mode='before')
    @classmethod
    def validate_positive_float(cls, v):
        fv = float(v)
        if fv <= 0:
            raise ValueError(f'{fv} must be positive')
        return fv

    @field_validator('REDIS_DB')
    @classmethod
    def validate_non_negative_int(cls, v):
        if v < 0:
            raise ValueError(f'{v} must be non-negative')
        return v

    @field_validator('WORKFLOW_REDIS_POOL_SIZE')
    @classmethod
    def validate_workflow_redis_pool_size(cls, v):
        if v < 10 or v > 20:
            raise ValueError('WORKFLOW_REDIS_POOL_SIZE must be between 10 and 20')
        return v

    @field_validator('CACHE_MIN_SIZE', 'CACHE_MAX_SIZE_LIMIT', mode='before')
    @classmethod
    def validate_optional_cache_bounds(cls, v):
        if v is None or v == "":
            return None
        iv = int(v)
        if iv <= 0:
            raise ValueError(f'{iv} must be positive')
        return iv

    @field_validator('ENVIRONMENT', mode='before')
    @classmethod
    def validate_environment(cls, v):
        if isinstance(v, str):
            v = v.lower()
        return v

    @property
    def cors_origins_list(self) -> List[str]:
        """获取CORS允许的源列表"""
        if isinstance(self.BACKEND_CORS_ORIGINS, str):
            return json.loads(self.BACKEND_CORS_ORIGINS)
        return self.BACKEND_CORS_ORIGINS

    @property
    def geoscene_center_list(self) -> List[float]:
        """获取GeoScene默认中心点列表"""
        if isinstance(self.GEOSCENE_DEFAULT_CENTER, str):
            return json.loads(self.GEOSCENE_DEFAULT_CENTER)
        return self.GEOSCENE_DEFAULT_CENTER

    @property
    def geoscene_is_mock(self) -> bool:
        """判断是否为Mock模式：无有效API Key且非Enterprise认证模式"""
        if self.GEOSCENE_AUTH_MODE == "enterprise":
            # Enterprise 模式下，检查账号密码是否已配置
            return not (self.GEOSCENE_USERNAME.strip() and self.GEOSCENE_PASSWORD.strip())
        # API Key 模式
        key = (self.GEOSCENE_API_KEY or "").strip()
        if not key:
            return True
        normalized = key.upper()
        mock_tokens = {
            "YOUR_GEOSCENE_API_KEY_HERE",
            "DEV_MOCK_GEOSCENE_KEY",
            "DEV_MOCK_KEY_REPLACE_FOR_PROD",
        }
        return normalized in mock_tokens

    @property
    def geoscene_token_url(self) -> str:
        """获取GeoScene Enterprise Token服务URL
        GeoScene Enterprise Token端点: {portalUrl}/sharing/rest/generateToken
        """
        if self.GEOSCENE_TOKEN_URL and self.GEOSCENE_TOKEN_URL.strip():
            return self.GEOSCENE_TOKEN_URL.strip()
        portal = self.GEOSCENE_PORTAL_URL.rstrip("/")
        return f"{portal}/sharing/rest/generateToken"

    @property
    def is_development(self) -> bool:
        """是否为开发环境"""
        return self.ENVIRONMENT == "development"

    @property
    def is_testing(self) -> bool:
        """是否为测试环境"""
        return self.ENVIRONMENT == "testing"

    @property
    def is_production(self) -> bool:
        """是否为生产环境"""
        return self.ENVIRONMENT == "production"

    @property
    def ip_whitelist_set(self) -> Set[str]:
        return {item.strip() for item in self.AUTH_IP_WHITELIST.split(",") if item.strip()}

    @property
    def ip_blacklist_set(self) -> Set[str]:
        return {item.strip() for item in self.AUTH_IP_BLACKLIST.split(",") if item.strip()}

    def get_env_file(self) -> str:
        """根据环境获取配置文件路径"""
        if self.ENVIRONMENT == "development":
            return str(self.ENV_DIR / ".env.development")
        elif self.ENVIRONMENT == "testing":
            return str(self.ENV_DIR / ".env.testing")
        elif self.ENVIRONMENT == "production":
            return str(self.ENV_DIR / ".env.production")
        return str(self.ENV_DIR / ".env")

# 根据环境变量获取当前环境
environment = os.getenv("ENVIRONMENT", "development").lower()

# 根据环境加载配置 - 优先使用后端专用配置文件
backend_env_file_map = {
    "development": str(ENV_DIR_PATH / ".env.backend.development"),
    "testing": str(ENV_DIR_PATH / ".env.backend.testing"),
    "production": str(ENV_DIR_PATH / ".env.backend.production")
}

# 优先使用后端专用的环境配置文件，如果不存在则使用默认 .env
current_env_file = backend_env_file_map.get(environment, str(ENV_DIR_PATH / ".env"))
if not Path(current_env_file).exists():
    current_env_file = str(ENV_DIR_PATH / ".env")

class EnvironmentSettings(Settings):
    """环境特定的配置类"""
    model_config = SettingsConfigDict(
        extra='ignore',  # 忽略额外的环境变量（如前端VITE_开头的变量）
        env_file=current_env_file,
        env_file_encoding="utf-8",
        case_sensitive=True
    )

# 创建配置实例
settings = EnvironmentSettings()

# 确保目录存在
settings.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.ANDROID_APK_DIR.mkdir(parents=True, exist_ok=True)

# 打印当前环境信息
if settings.DEBUG:
    print(f"🚀 当前环境: {settings.ENVIRONMENT}")
    print(f"📝 配置文件: {current_env_file}")
    print(f"🔧 调试模式: {settings.DEBUG}")
