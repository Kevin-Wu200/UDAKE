# 灾难恢复流程

## 执行步骤
1. 宣布进入灾备状态，冻结发布。
2. 执行数据与配置恢复。
3. 恢复完成后执行健康检查。
4. 重新挂载流量并观察 30 分钟。
5. 输出恢复报告与改进动作。

## 建议命令
```bash
./deployment/scripts/stop.sh
./deployment/scripts/test_backup_restore.sh
./deployment/scripts/start.sh
./deployment/scripts/run_checks_stage2.sh
```
