# 部署脚本使用说明（阶段1+2）

## 脚本列表
- `install.sh`：安装与环境检查
- `configure.sh`：配置检查与参数校验
- `start.sh`：启动服务
- `stop.sh`：停止服务
- `update.sh`：更新并自动回滚
- `backup.sh`：执行备份
- `restore.sh`：从指定备份恢复
- `rollback.sh`：按回滚策略自动回滚
- `test_alerts.sh`：告警规则校验测试
- `test_logging.sh`：日志写入与采集链路测试
- `run_checks.sh`：一键执行阶段1关键校验
- `test_autoscaling.sh`：扩缩容策略校验
- `verify_performance_baseline.sh`：性能基线配置校验
- `test_backup_restore.sh`：备份恢复策略校验
- `test_disaster_recovery.sh`：灾备文档与流程校验
- `run_checks_stage2.sh`：一键执行阶段2关键校验

## 使用顺序
1. `./deployment/scripts/install.sh`
2. `./deployment/scripts/configure.sh`
3. `./deployment/scripts/start.sh`
4. `./deployment/scripts/run_checks.sh`
5. `./deployment/scripts/run_checks_stage2.sh`

## 变量说明
- `DEPLOY_TARGET_DIR`：部署目标目录，默认 `deployment/spatiotemporal_kriging`
- `LOG_DIR`：日志测试输出目录
