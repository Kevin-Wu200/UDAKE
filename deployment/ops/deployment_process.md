# 部署流程文档

## 标准发布流程
1. 预检查：`./deployment/scripts/install.sh`
2. 配置校验：`./deployment/scripts/configure.sh`
3. 启动服务：`./deployment/scripts/start.sh`
4. 阶段1检查：`./deployment/scripts/run_checks.sh`
5. 阶段2检查：`./deployment/scripts/run_checks_stage2.sh`

## 变更控制要求
- 发布前完成变更单审批与回滚点确认。
- 发布窗口内必须有值班运维与开发在场。
- 发布后 30 分钟内持续观察告警与关键性能指标。

## 回退策略
- 发布失败时优先执行 `./deployment/scripts/rollback.sh`。
- 回滚后执行健康检查并记录故障单。
