# 深度学习模块 FAQ

## Q1: 没有 CUDA 时是否可运行？
可以，`DeviceManager` 会自动降级到 CPU；Apple Silicon 会优先尝试 MPS。

## Q2: 是否必须安装 PyTorch Lightning？
不是。当前训练器是 Lightning 风格轻量实现，支持无缝替换为正式 Lightning 训练循环。

## Q3: 如何覆盖配置中的 batch size？
设置环境变量：`DL_TRAINING__BATCH_SIZE=64`。

## Q4: 推理是否支持异步？
支持，使用 `AsyncInferenceEngine.predict_async` 即可。
