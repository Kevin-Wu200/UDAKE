#!/usr/bin/env python3
"""
后端服务启动脚本
"""
import warnings
import uvicorn
from app.config import settings

# 抑制 macOS LibreSSL 与 urllib3 v2 的兼容性警告（不影响功能）
warnings.filterwarnings("ignore", message=".*urllib3.*LibreSSL.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="urllib3")

if __name__ == "__main__":
    print(f"🚀 启动 {settings.APP_NAME}")
    print(f"📍 地址: http://{settings.HOST}:{settings.PORT}")
    print(f"📖 API文档: http://{settings.HOST}:{settings.PORT}/docs")

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )
