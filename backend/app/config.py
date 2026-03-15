"""
配置文件
支持多环境配置：development（开发）、testing（测试）、production（生产）
"""
from pydantic_settings import BaseSettings
from pydantic import field_validator, Field
from typing import List, Optional, Union, Literal
from pathlib import Path
import json
import os

class Settings(BaseSettings):
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
    BACKEND_CORS_ORIGINS: Union[str, List[str]] = '["http://localhost:5173","http://localhost:3000","http://127.0.0.1:5173"]'

    # 文件上传配置
    MAX_FILE_SIZE_MB: int = 100

    # 文件路径配置
    BASE_DIR: Path = Path(__file__).parent.parent
    RESULTS_DIR: Path = BASE_DIR / "app" / "结果文件"
    DATA_DIR: Path = BASE_DIR.parent / "data_samples"

    # 任务配置
    MAX_CONCURRENT_TASKS: int = 5
    TASK_TIMEOUT: int = 3600

    # 克里金配置
    DEFAULT_VARIOGRAM_MODEL: str = "spherical"
    GRID_RESOLUTION: int = 100

    # ArcGIS配置
    ARCGIS_API_KEY: str = "YOUR_ARCGIS_API_KEY_HERE"
    ARCGIS_PORTAL_URL: str = "https://www.arcgis.com"
    ARCGIS_ENV: str = "development"
    ARCGIS_DEFAULT_BASEMAP: str = "streets-vector"
    ARCGIS_DEFAULT_CENTER: Union[str, List[float]] = "[139.767125,35.681236]"
    ARCGIS_DEFAULT_ZOOM: int = 10

    # 高德地图配置
    AMAP_API_KEY: str = "2f3f114aa5671425aa3c52f707d741c5"
    AMAP_SECURITY_CODE: str = "10b5ef21f6b36d09e24d7b076d35dccc"

    # 天地图配置
    TIANDITU_API_KEY: str = "YOUR_TIANDITU_API_KEY_HERE"
    TIANDITU_TOKEN: Optional[str] = None

    # AI扩展模块配置
    AI_MODEL_PATH: Optional[str] = None
    AI_CACHE_ENABLED: bool = True
    AI_MAX_BATCH_SIZE: int = 100

    # 数据库配置（可选）
    DATABASE_URL: Optional[str] = None
    REDIS_URL: Optional[str] = None

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
                return ["http://localhost:5173"]
        return v

    @field_validator('ARCGIS_DEFAULT_CENTER', mode='before')
    @classmethod
    def parse_center(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [139.767125, 35.681236]
        return v

    @field_validator('MAX_CONCURRENT_TASKS', 'TASK_TIMEOUT', 'GRID_RESOLUTION', 'MAX_FILE_SIZE_MB', 'AI_MAX_BATCH_SIZE')
    @classmethod
    def validate_positive_int(cls, v):
        if v <= 0:
            raise ValueError(f'{v} must be positive')
        return v

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
    def arcgis_center_list(self) -> List[float]:
        """获取ArcGIS默认中心点列表"""
        if isinstance(self.ARCGIS_DEFAULT_CENTER, str):
            return json.loads(self.ARCGIS_DEFAULT_CENTER)
        return self.ARCGIS_DEFAULT_CENTER

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

    def get_env_file(self) -> str:
        """根据环境获取配置文件路径"""
        if self.ENVIRONMENT == "development":
            return ".env.development"
        elif self.ENVIRONMENT == "testing":
            return ".env.testing"
        elif self.ENVIRONMENT == "production":
            return ".env.production"
        return ".env"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

# 根据环境变量获取当前环境
environment = os.getenv("ENVIRONMENT", "development").lower()

# 根据环境加载配置
env_file_map = {
    "development": ".env.development",
    "testing": ".env.testing",
    "production": ".env.production"
}

# 优先使用环境特定的配置文件，如果不存在则使用默认 .env
current_env_file = env_file_map.get(environment, ".env")
if not Path(current_env_file).exists():
    current_env_file = ".env"

class EnvironmentSettings(Settings):
    """环境特定的配置类"""
    class Config:
        env_file = current_env_file
        env_file_encoding = "utf-8"
        case_sensitive = True

# 创建配置实例
settings = EnvironmentSettings()

# 确保目录存在
settings.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)

# 打印当前环境信息
if settings.DEBUG:
    print(f"🚀 当前环境: {settings.ENVIRONMENT}")
    print(f"📝 配置文件: {current_env_file}")
    print(f"🔧 调试模式: {settings.DEBUG}")
