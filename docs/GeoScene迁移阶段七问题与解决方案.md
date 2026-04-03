# GeoScene 迁移阶段七问题与解决方案

## 1. 背景
- 阶段目标：完成任务 31-34（高级功能测试、性能与兼容性测试、代码审查与提交、合并与文档收尾）。
- 执行日期：2026-04-03
- 执行分支：`feature/geoscene-migration`

## 2. 关键问题与处理

### 问题 A：深度学习测试启动失败（前置目录缺失）
- 现象：`pytest tests/deep_learning -q` 启动时报错，`conftest.py` 引导后端挂载静态目录时发现 `android/app/build/outputs/apk/release` 不存在。
- 影响：无法进入深度学习模型加载、推理、可视化相关测试。
- 处理：
  1. 先执行 `cd android && ./gradlew assembleDebug`，确认 Android 构建链路可用。
  2. 创建缺失目录 `android/app/build/outputs/apk/release`。
  3. 重新执行 `./venv/bin/pytest tests/deep_learning -q`。
- 结果：`57 passed in 4.25s`。

### 问题 B：跨浏览器测试初次失败（Firefox/WebKit 未安装）
- 现象：Playwright 运行 `firefox` 与 `webkit` 项目时提示浏览器可执行文件不存在。
- 影响：无法完成 Firefox/Safari 兼容性验证。
- 处理：
  1. 执行 `npx playwright install firefox webkit` 安装浏览器依赖。
  2. 重新执行 `npx playwright test --config configs/playwright.config.ts --project=chromium --project=firefox --project=webkit tests/e2e/i18n-compatibility.test.ts`。
- 结果：`6 passed`，三浏览器项目全部通过。

### 问题 C：测试产物污染工作区
- 现象：测试生成 `logs/tensorboard/*`、`reports/memory/*` 等本地产物。
- 影响：容易被误纳入提交。
- 处理：在 `.gitignore` 增加：
  - `logs/tensorboard/`
  - `reports/memory/`
- 结果：阶段测试产物与代码提交隔离。

## 3. 测试与验证清单
- 深度学习能力：`./venv/bin/pytest tests/deep_learning -q`（57 通过）
- 导出能力：
  - `npx vitest --config configs/vitest.config.js --run tests/exportenhancer.test.js tests/VariogramChart.test.ts tests/ParameterImpactPreview.test.ts`（53 通过）
- GeoScene/地图相关回归：
  - `npx vitest --config configs/vitest.config.js --run tests/config-api.test.js tests/preferencespanel.test.js tests/store.test.js tests/gps-frontend.test.js`（101 通过）
- Android 打包：`cd android && ./gradlew assembleDebug`（BUILD SUCCESSFUL）
- 性能验证：
  - `npm run test:performance`（43 通过）
  - `npm run track:benchmark`（passed=true）
  - `npm run navigation:stability:test`（accuracy=100%, passed=true）
  - `node scripts/memory-leak-detection.js --duration-sec=10 --interval-ms=1000 --max-projected-24h-mb=200 --max-growth-per-hour-mb=200`（potential_leak=false）
- 兼容性验证：
  - `chromium/firefox/webkit` 三项目 Playwright 通过
  - Edge 与 Chromium 内核保持等价兼容性验证路径

## 4. 合并说明
- 本阶段完成于 `feature/geoscene-migration` 分支并提交。
- 合并到 `main` 按团队集成窗口执行，当前无已知阻塞项。
