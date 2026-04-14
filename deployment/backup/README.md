# 备份策略（阶段2）

## 文件说明
- `backup_strategy.md`：备份方案设计说明
- `backup_policy.yml`：频率、保留与校验配置
- `restore_validation.md`：恢复测试与完整性验证流程

## 执行命令
```bash
./deployment/scripts/backup.sh
./deployment/scripts/test_backup_restore.sh
```
