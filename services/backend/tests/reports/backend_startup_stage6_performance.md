# 后端服务启动优化第六章性能报告

- 迭代次数: 20
- 启动时间对比（legacy vs optimized）: 0.000ms -> 0.003ms
- 启动链路差值: 0.003ms
- Redis 连接检测均值: 0.000ms
- 内存峰值: 2.55 KiB

## 明细

```json
{
  "iterations": 20,
  "startup_time_compare": {
    "legacy_baseline": {
      "mean_ms": 0.00016455000000012432,
      "min_ms": 0.00012499999999665556,
      "max_ms": 0.0004159999999961417
    },
    "optimized_pipeline": {
      "mean_ms": 0.002912549999999417,
      "min_ms": 0.002415999999998142,
      "max_ms": 0.008750000000001812
    },
    "delta_ms": 0.0027479999999992927,
    "ratio": 17.70009115768591
  },
  "redis_connection_performance": {
    "mean_ms": 8.340000000085779e-05,
    "min_ms": 4.099999999923609e-05,
    "max_ms": 0.00020800000000154029
  },
  "memory_usage_kib": {
    "current_kib": 2.2138671875,
    "peak_kib": 2.5498046875
  }
}
```
