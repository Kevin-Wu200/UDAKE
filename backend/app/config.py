"""
配置文件
"""
from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "智能不确定性驱动空间决策平台"
    VERSION: str = "1.0.0"
    DEBUG: bool = True

    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS配置
    CORS_ORIGINS: list = ["*"]

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
    ARCGIS_API_KEY: str = "YOUR_ARCGIS_API_KEY_PLACEHOLDER"
    ARCGIS_PORTAL_URL: str = "https://www.arcgis.com"
    ARCGIS_ENV: str = "development"
    ARCGIS_DEFAULT_BASEMAP: str = "streets-vector"
    ARCGIS_DEFAULT_CENTER: list = [139.767125, 35.681236]
    ARCGIS_DEFAULT_ZOOM: int = 10

    class Config:
        env_file = ".env"

settings = Settings()

# 确保目录存在
settings.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
