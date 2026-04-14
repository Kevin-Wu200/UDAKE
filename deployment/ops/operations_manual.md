# 运维手册

## 快速命令
```bash
# 基础部署
./deployment/scripts/install.sh
./deployment/scripts/configure.sh
./deployment/scripts/start.sh

# 阶段校验
./deployment/scripts/run_checks.sh
./deployment/scripts/run_checks_stage2.sh

# 备份与恢复
./deployment/scripts/backup.sh
./deployment/scripts/test_backup_restore.sh

# 灾备演练
./deployment/scripts/test_disaster_recovery.sh
```

## 值班操作清单
1. 每班核对告警面板与服务健康。
2. 每日确认备份与校验结果。
3. 每周确认扩缩容阈值与性能基线趋势。
4. 每月执行灾备演练并沉淀复盘记录。
