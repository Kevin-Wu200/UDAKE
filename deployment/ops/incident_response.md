# 故障处理文档

## 故障等级
- P1：核心服务不可用或数据风险。
- P2：核心功能降级、错误率明显上升。
- P3：非核心异常或可绕过问题。

## 标准处理步骤
1. 告警确认：确认告警来源与影响范围。
2. 快速止损：限流、摘流量、回滚或扩容。
3. 根因定位：结合日志、指标、变更记录排查。
4. 服务恢复：恢复后至少观察 30 分钟。
5. 复盘改进：输出 RCA、改进项与截止时间。

## 常见故障快速指令
```bash
./deployment/scripts/rollback.sh
./deployment/scripts/test_alerts.sh
./deployment/scripts/test_logging.sh
```
