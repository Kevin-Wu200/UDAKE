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
- 强化学习采样优化（SamplingEnv、PPO/DQN/A2C、多智能体协作、在线学习）
- 不确定性量化模型（BNN、MC Dropout、Deep Ensemble、EDL）
- 不确定性聚合/校准/评估与系统集成工具
- 模型融合与系统集成（多策略融合、权重学习、自适应融合、模型管理与服务化接口）

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
python3 deep_learning/examples/anomaly_vae_full_demo.py
python3 deep_learning/examples/anomaly_gcae_full_demo.py
python3 deep_learning/examples/anomaly_gan_full_demo.py
python3 deep_learning/examples/anomaly_contrastive_full_demo.py
python3 deep_learning/examples/anomaly_multi_model_comparison_demo.py
python3 deep_learning/examples/anomaly_batch_processing_demo.py
python3 deep_learning/examples/anomaly_custom_visualization_demo.py
python3 deep_learning/examples/anomaly_performance_optimization_demo.py
python3 deep_learning/examples/verify_anomaly_examples.py
```

## 阶段5快速命令

```bash
python3 deep_learning/training/train_sampling_rl.py --model ppo --episodes 30 --size 24
python3 deep_learning/inference/run_sampling_rl_inference.py --model ppo --n 12 --strategy hybrid
python3 deep_learning/examples/sampling_rl_demo.py
python3 deep_learning/examples/rl_adapter_usage_demo.py
```

## 阶段4快速命令

```bash
python3 deep_learning/examples/uncertainty_training_demo.py
python3 deep_learning/examples/uncertainty_inference_demo.py
```

## 阶段6快速命令

```bash
python3 deep_learning/training/train_spatiotemporal.py --model st_transformer --epochs 20 --seq-len 24 --horizon 6
python3 deep_learning/inference/run_spatiotemporal_inference.py --model gcn_lstm --seq-len 24 --horizon 6
```

## 阶段7快速命令

```bash
python3 deep_learning/examples/fusion_adapter_usage_demo.py
python3 -m pytest tests/deep_learning/test_fusion_system.py -q
python3 -m pytest tests/deep_learning/test_dl_service_fusion_api.py -q
```
