# 回滚方案（阶段1）

## 回滚策略
- 蓝绿或滚动发布失败时，优先回滚到最近一次可用备份。
- 触发条件来自 `rollback-trigger.env`：健康检查失败次数、5xx 比例、P95 时延。
- 回滚前必须保存当前失败版本快照，便于故障复盘。

## 回滚流程
1. 判定触发条件达成并冻结发布。
2. 执行 `deployment/scripts/backup.sh` 保存失败现场。
3. 执行 `deployment/scripts/rollback.sh` 回滚到最近可用备份。
4. 验证 `http://127.0.0.1/health` 与关键业务接口。
5. 发布回滚结果并启动故障复盘。

## 回滚数据准备
- 数据库：`postgres.dump`
- 缓存：`redis.rdb`
- 配置：`configs.tgz`
- 校验：`SHA256SUMS`

## 培训要求
- 运维人员每月至少一次回滚演练。
- 新成员上线前必须通过回滚演练清单。
