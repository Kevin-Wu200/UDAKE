# 日志收集配置（阶段1）

## 文件说明
- `architecture.md`：日志采集架构与保留策略
- `fluent-bit.conf`：日志采集配置
- `parsers.conf`：日志解析规则
- `index-template.json`：索引模板
- `log_alert_rules.yml`：日志告警规则
- `retention-policy.yml`：日志保留策略

## 日志链路测试
```bash
./deployment/scripts/test_logging.sh
```
