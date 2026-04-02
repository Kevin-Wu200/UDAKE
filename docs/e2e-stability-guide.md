# E2E 测试稳定性指南

## 目标
- 降低偶发失败（flaky）
- 缩短 CI 执行耗时
- 提升失败可诊断性

## 已落地策略
1. 智能等待
- 使用 `gotoAndWaitForAppReady` 替代直接 `page.goto`。
- 使用 `waitForApiResponse` 将点击动作与关键接口响应绑定，避免“点到了但请求未发出/未返回”的竞态。

2. 智能重试
- 使用 `retryWithBackoff` 对易受 UI 抖动影响的动作做指数退避重试。
- 在控制台输出 `[e2e-retry]` 日志用于失败定位。

3. 测试数据隔离
- 使用 `createTestDataFactory` 生成带测试命名空间的唯一 ID。
- 避免跨用例共用固定 workflow_id / run_id 导致的数据串扰。

4. 环境健康检查
- 在 `configs/playwright.global-setup.ts` 中对每个 `baseURL` 做带退避的可用性探测。
- 环境未就绪时尽早失败，避免进入用例后才随机超时。

5. 执行与报告优化
- Playwright 配置开启 `fullyParallel`、CI `workers=2`、`retries=2`。
- 报告同时输出 `html/json/junit`。
- `npm run test:e2e:report` 汇总 flaky/failed 测试，便于跟踪趋势。

## 编写新 E2E 用例建议
1. 页面进入统一使用 `gotoAndWaitForAppReady`。
2. 关键业务按钮点击统一使用 `waitForApiResponse` 包裹。
3. 如存在偶发点击失败，使用 `retryWithBackoff`，并限定在最小操作范围。
4. 每个用例用 `createTestDataFactory(testInfo.title)` 生成隔离数据。
5. 如果需要新增高耗时场景，优先拆分到独立配置与 CI 任务，避免拖慢主链路。
