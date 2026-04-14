# 自动扩缩容配置（阶段2）

## 文件说明
- `autoscaling_policy.yml`：扩缩容策略与阈值配置
- `performance_baseline.yml`：性能基线定义与告警阈值
- `baseline_review.md`：性能趋势分析与基线更新流程

## 校验命令
```bash
./deployment/scripts/test_autoscaling.sh
./deployment/scripts/verify_performance_baseline.sh
```
