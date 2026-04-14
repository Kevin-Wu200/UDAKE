# 告警通知模板

## 钉钉/企业微信/Slack 文本模板

```
[{{ .Status | toUpper }}] {{ .CommonLabels.alertname }}
级别: {{ .CommonLabels.severity }}
服务: {{ .CommonLabels.service }}
实例: {{ .CommonLabels.instance }}
摘要: {{ .CommonAnnotations.summary }}
详情: {{ .CommonAnnotations.description }}
开始时间: {{ (index .Alerts 0).StartsAt }}
```

## 通知策略
- critical：值班群 + 电话/短信。
- warning：值班群。
- resolved：仅群通知，不触发电话。
