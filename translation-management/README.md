# 翻译管理系统（TMS）集成说明

本目录用于统一管理前端国际化资源，支持导出、校验和对接外部翻译平台。

## 命令

- `npm run i18n:tms:export`
  - 从 `apps/frontend/js/utils/I18n.ts` 导出 `zh-CN`、`en-US` 基准资源到 `translation-management/source/`。
- `npm run i18n:tms:validate`
  - 校验 `zh-TW`、`ja-JP`、`ko-KR` 是否与基准键集一致，生成报告到 `translation-management/reports/validation.json`。
- `npm run i18n:tms:validate:strict`
  - 与上面相同，但发现缺失键时返回非零退出码，适用于 CI。

## 外部平台

- Crowdin 配置文件：`/.crowdin.yml`
- 使用前请设置环境变量：
  - `CROWDIN_PROJECT_ID`
  - `CROWDIN_PERSONAL_TOKEN`
