# Deep Learning 基础架构

本目录提供深度学习基础设施与阶段2空间插值神经网络能力，包括：

- 数据预处理框架（标准化、缩放、增强、划分、GeoJSON 转换、缓存）
- 训练框架（Lightning 风格训练器、TensorBoard、Checkpoint、早停、调度）
- 模型管理（注册、版本管理、序列化、导出、量化）
- 推理服务（批处理、流式、异步）
- 配置系统（YAML 模板、继承、环境变量覆盖）
- 监控系统（指标、资源、告警、仪表板）
- 空间插值模型（GNN-Kriging、Attention-Kriging、Residual-Kriging）
- 异常检测模型（VAE、GCAE、GAN、Contrastive）
- 异常数据与评估工具（合成异常、标注、评估报告、实时告警）
- 不确定性量化模型（BNN、MC Dropout、Deep Ensemble、EDL）
- 不确定性聚合/校准/评估与系统集成工具

## 快速开始

```bash
python3 -m pytest tests/deep_learning -q
```

## 阶段2快速命令

```bash
python3 deep_learning/training/train_spatial_interpolation.py --model gnn --epochs 20
python3 deep_learning/inference/run_spatial_interpolation_inference.py --model residual --grid-size 16
```

## 阶段3快速命令

```bash
python3 deep_learning/examples/anomaly_training_demo.py
python3 deep_learning/examples/anomaly_inference_demo.py
```

## 阶段4快速命令

```bash
python3 deep_learning/examples/uncertainty_training_demo.py
python3 deep_learning/examples/uncertainty_inference_demo.py
```
