# GPU技术调研报告

## 1. 候选框架
- CUDA：生态成熟，NVIDIA 场景性能强。
- OpenCL：跨厂商，但开发复杂度较高。
- ROCm：AMD 生态，部署场景依赖硬件。

## 2. Python 生态候选
- CuPy：NumPy 风格接口，迁移成本低。
- Numba：JIT 灵活，适合自定义 kernel。
- PyTorch：张量能力强，但对纯数值服务场景偏重。

## 3. 选型结论
- 当前版本采用 `CuPy + NumPy 回退` 模式：
  - 有 GPU：优先 GPU 计算。
  - 无 GPU：自动回退 CPU，确保服务可用。
- 原因：
  - 与现有 NumPy 代码兼容性高。
  - 便于分阶段落地，不阻塞现网功能。
