"""
UDAKE Siri 智能助手模块

一个独立的智能交互模块，通过标准 API 接口与前端解耦通信。
支持自然语言查询、系统功能调用、文档检索等能力。

架构：
  - api.py         REST API 路由
  - service.py     核心服务逻辑
  - llm_client.py  Ollama LLM 客户端
  - retriever.py   文档检索器
  - intent_parser.py 意图识别与分类
  - security.py    安全防护层
  - knowledge_store.py 知识库读写管理
  - models.py      Pydantic 数据模型
  - config.py      模块配置项
"""
