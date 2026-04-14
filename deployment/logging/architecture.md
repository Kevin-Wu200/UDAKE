# 日志收集架构（阶段1）

## 架构设计
- 日志源：`backend`、`nginx`、`postgres`、`redis` 容器标准输出与文件日志。
- 采集层：Fluent Bit（Daemon/Sidecar）收集并标准化。
- 存储层：Elasticsearch/OpenSearch（短期检索）+ 对象存储（长期归档）。
- 查询分析：Kibana/OpenSearch Dashboards。
- 告警：基于错误关键词、错误率与日志吞吐突增触发。

## 日志索引策略
- 索引命名：`udake-logs-YYYY.MM.DD`
- 分片建议：1-3（按节点规模）
- 字段规范：`timestamp`、`level`、`service`、`trace_id`、`message`、`host`

## 保留策略
- 热数据：7 天
- 温数据：30 天
- 冷归档：180 天
- 超期数据自动删除
