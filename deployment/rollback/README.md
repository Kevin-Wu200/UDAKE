# 回滚方案（阶段1）

## 文件说明
- `rollback-trigger.env.example`：回滚触发条件模板
- `rollback_plan.md`：回滚策略、流程、培训要求

## 回滚执行
```bash
cp deployment/rollback/rollback-trigger.env.example deployment/rollback/rollback-trigger.env
./deployment/scripts/rollback.sh
```
