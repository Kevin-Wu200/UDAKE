# Deep Learning 基础架构

本目录提供阶段1所需的深度学习基础设施，包括：

- 数据预处理框架（标准化、缩放、增强、划分、GeoJSON 转换、缓存）
- 训练框架（Lightning 风格训练器、TensorBoard、Checkpoint、早停、调度）
- 模型管理（注册、版本管理、序列化、导出、量化）
- 推理服务（批处理、流式、异步）
- 配置系统（YAML 模板、继承、环境变量覆盖）
- 监控系统（指标、资源、告警、仪表板）

## 快速开始

```bash
python3 -m pytest tests/deep_learning -q
```
