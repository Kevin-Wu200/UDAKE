"""
Siri 助手模块配置

所有配置项均可通过环境变量覆盖，前缀 SIRI_。
"""

import os
from pathlib import Path
from typing import Optional


class SiriAssistantConfig:
    """Siri 助手配置（可通过环境变量覆盖）"""

    # --- Ollama 配置 ---
    OLLAMA_HOST: str = os.getenv("SIRI_OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("SIRI_OLLAMA_MODEL", "qwen3:8b")
    OLLAMA_REQUEST_TIMEOUT: int = int(os.getenv("SIRI_OLLAMA_TIMEOUT", "60"))
    OLLAMA_TEMPERATURE: float = float(os.getenv("SIRI_OLLAMA_TEMPERATURE", "0.3"))
    OLLAMA_MAX_TOKENS: int = int(os.getenv("SIRI_OLLAMA_MAX_TOKENS", "1024"))

    # --- 检索配置 ---
    DOCS_DIR: Path = Path(os.getenv("SIRI_DOCS_DIR", str(Path(__file__).resolve().parents[4] / "docs")))
    HELPER_FILE: Path = Path(os.getenv("SIRI_HELPER_FILE", str(DOCS_DIR / "Helper.md")))
    MAX_RETRIEVAL_RESULTS: int = int(os.getenv("SIRI_MAX_RESULTS", "5"))
    RETRIEVAL_CACHE_ENABLED: bool = os.getenv("SIRI_CACHE_ENABLED", "true").lower() == "true"

    # --- 安全配置 ---
    BLOCKED_KEYWORDS: list[str] = os.getenv(
        "SIRI_BLOCKED_KEYWORDS",
        "exploit,hack,bypass,inject,override,system prompt,ignore previous,"
        "disregard above,forget instructions"
    ).split(",")
    MAX_QUERY_LENGTH: int = int(os.getenv("SIRI_MAX_QUERY_LENGTH", "2000"))
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("SIRI_RATE_LIMIT", "30"))

    # --- 知识库配置 ---
    HELPER_MAX_FILE_SIZE_MB: int = int(os.getenv("SIRI_HELPER_MAX_MB", "5"))
    HELPER_TEMPLATE: str = """# UDAKE 智能助手知识库

> 此文件由 UDAKE Siri 助手自动管理，包含常见问题与答案。
> 最后更新时间: {update_time}

{entries}

---

## 模板说明

每一条目格式：
```
### Q: {问题标题}
{问题描述}

**A:** {答案}
```
"""
    HELPER_ENTRY_TEMPLATE: str = """### Q: {title}
{question}

**A:** {answer}
"""

    # --- 日志配置 ---
    LOG_LEVEL: str = os.getenv("SIRI_LOG_LEVEL", "INFO")
    INTERACTION_LOG_DIR: Path = Path(
        os.getenv("SIRI_LOG_DIR", str(Path(__file__).resolve().parents[4] / "logs" / "siri"))
    )


# 全局配置实例
siri_config = SiriAssistantConfig()
