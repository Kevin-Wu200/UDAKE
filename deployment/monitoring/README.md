# 监控告警配置（阶段1）

## 文件说明
- `metrics_design.md`：监控指标设计
- `prometheus.yml`：采集配置（系统 + 应用 + 性能）
- `alert_rules.yml`：告警规则（系统/应用/性能/错误）
- `alertmanager.yml`：告警通知路由
- `notification_template.md`：通知模板

## 告警测试
```bash
./deployment/scripts/test_alerts.sh
```
