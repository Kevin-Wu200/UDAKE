# UDAKE Kubernetes 部署架构设计文档

## 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 创建日期 | 2026-05-23 |
| 作者 | UDAKE 开发团队 |
| 状态 | 规划阶段 |

---

## 一、概述

### 1.1 目标

将 UDAKE 平台从单机 Docker Compose 部署升级为 Kubernetes 容器编排架构，实现：
- 高可用（HA）生产级部署
- 自动扩缩容应对计算密集型任务
- 滚动更新零停机
- 统一配置管理与密钥保护
- 多环境一致性（开发/测试/生产）

### 1.2 当前部署架构

```
Docker Compose (单机)
├── backend (FastAPI :8000)
├── nginx (反向代理 :6060)
└── (PostgreSQL + Redis 需外挂)
```

### 1.3 目标 K8s 架构

```
┌────────────────────────────────────────────────┐
│                   Ingress                       │
│              (nginx-ingress / Traefik)           │
│              TLS termination + routing           │
└────────────┬───────────────────────────────────┘
             │
    ┌────────┴────────┐
    │                 │
    ▼                 ▼
┌─────────┐     ┌──────────┐
│ Frontend │     │ Backend  │
│ (nginx)  │     │(FastAPI) │
│  Replicas│     │ Replicas │
└─────────┘     └────┬─────┘
                      │
           ┌──────────┼──────────┐
           ▼          ▼          ▼
      ┌────────┐ ┌────────┐ ┌────────┐
      │PostgreSQL│ │ Redis  │ │  PV    │
      │ (Stateful)│ │(Stateful)│ │(共享)  │
      └────────┘ └────────┘ └────────┘
```

---

## 二、Helm Chart 结构设计

### 2.1 Chart 目录结构

```
deployment/helm/udake/
├── Chart.yaml
├── values.yaml              # 默认配置
├── values-dev.yaml          # 开发环境覆盖
├── values-prod.yaml         # 生产环境覆盖
├── templates/
│   ├── _helpers.tpl         # 模板辅助函数
│   ├── namespace.yaml       # 命名空间
│   ├── configmap.yaml       # 配置映射
│   ├── secret.yaml          # 密钥管理
│   ├── backend/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   ├── hpa.yaml         # 水平自动扩缩容
│   │   └── pdb.yaml         # Pod 中断预算
│   ├── frontend/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   └── configmap.yaml
│   ├── postgresql/
│   │   ├── statefulset.yaml
│   │   ├── service.yaml
│   │   └── pvc.yaml
│   ├── redis/
│   │   ├── statefulset.yaml
│   │   ├── service.yaml
│   │   └── pvc.yaml
│   └── ingress.yaml
```

### 2.2 关键 values.yaml 参数

```yaml
# 全局配置
global:
  environment: production
  imageRegistry: registry.example.com/udake
  imagePullSecrets:
    - name: regcred

# Backend 配置
backend:
  replicaCount: 3
  image:
    repository: udake-backend
    tag: latest
    pullPolicy: IfNotPresent
  resources:
    requests:
      cpu: "500m"
      memory: "1Gi"
    limits:
      cpu: "2000m"
      memory: "4Gi"
  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 10
    targetCPUUtilizationPercentage: 70
    targetMemoryUtilizationPercentage: 80
  health:
    livenessProbe:
      path: /health
      initialDelaySeconds: 30
      periodSeconds: 10
    readinessProbe:
      path: /ready
      initialDelaySeconds: 10
      periodSeconds: 5
    startupProbe:
      path: /health
      initialDelaySeconds: 15
      periodSeconds: 5
      failureThreshold: 30

# Frontend 配置
frontend:
  replicaCount: 2
  resources:
    requests:
      cpu: "100m"
      memory: "128Mi"
    limits:
      cpu: "500m"
      memory: "256Mi"

# PostgreSQL 配置
postgresql:
  enabled: true
  replicaCount: 1
  storage:
    size: 50Gi
    storageClass: standard
  auth:
    database: udake
    username: udake

# Redis 配置
redis:
  enabled: true
  replicaCount: 1
  storage:
    size: 20Gi
    storageClass: standard

# Ingress 配置
ingress:
  enabled: true
  className: nginx
  hosts:
    - host: udake.example.com
      paths:
        - path: /
          pathType: Prefix
          serviceName: frontend
        - path: /api
          pathType: Prefix
          serviceName: backend
  tls:
    - secretName: udake-tls
      hosts:
        - udake.example.com
```

---

## 三、服务发现与路由

### 3.1 Service 类型

| 服务 | Service 类型 | 端口 | 说明 |
|------|-------------|------|------|
| frontend | ClusterIP | 80 | 前端静态资源 |
| backend | ClusterIP | 8000 | FastAPI 后端 |
| postgresql | ClusterIP (Headless) | 5432 | 数据库 |
| redis | ClusterIP | 6379 | 缓存 |

### 3.2 Ingress 路由规则

- `/` → frontend service (静态资源 + SPA)
- `/api/*` → backend service (REST API)
- `/ws/*` → backend service (WebSocket 连接)
- `/metrics` → backend service (Prometheus 指标)
- `/health` → backend service (健康检查)

---

## 四、持久化存储

### 4.1 存储需求

| 组件 | 存储类型 | 容量 | 访问模式 |
|------|---------|------|---------|
| PostgreSQL | PVC (SSD) | 50Gi | ReadWriteOnce |
| Redis | PVC | 20Gi | ReadWriteOnce |
| 数据文件 | PV (共享) | 100Gi | ReadWriteMany |
| 结果文件 | PV (共享) | 100Gi | ReadWriteMany |
| 日志 | PV | 50Gi | ReadWriteMany |

### 4.2 备份策略

- PostgreSQL: 每日全量备份 + WAL 连续归档
- Redis: RDB 快照每 6 小时
- 数据文件: 每日增量同步至对象存储

---

## 五、自动扩缩容 (HPA)

### 5.1 扩缩容策略

```yaml
# CPU/内存指标
- type: Resource
  resource:
    name: cpu
    target:
      type: Utilization
      averageUtilization: 70

# 自定义指标（任务队列深度）
- type: Pods
  pods:
    metric:
      name: udake_task_queue_depth
    target:
      type: AverageValue
      averageValue: "5"
```

### 5.2 扩容触发条件

1. CPU 使用率 > 70% 持续 3 分钟
2. 内存使用率 > 80% 持续 3 分钟
3. 任务队列深度 > 5 持续 2 分钟
4. 请求延迟 P95 > 2s 持续 5 分钟

---

## 六、健康检查配置

| 探针 | 路径 | 初始延迟 | 周期 | 超时 | 失败阈值 |
|------|------|---------|------|------|---------|
| livenessProbe | /health | 30s | 10s | 5s | 3 |
| readinessProbe | /ready | 10s | 5s | 3s | 3 |
| startupProbe | /health | 15s | 5s | 3s | 30 |

---

## 七、滚动更新策略

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1          # 最多额外 Pod 数
    maxUnavailable: 0    # 零停机：不可用 Pod 为 0
```

### 蓝绿部署备选方案

- 使用 Istio VirtualService 实现流量切分
- 蓝绿环境：Active/Standby 双环境
- 回滚时间：< 30 秒

---

## 八、集群规格估算

### 8.1 最小生产集群（3 节点）

| 节点 | 角色 | vCPU | 内存 | 磁盘 |
|------|------|------|------|------|
| node-1 | 控制平面 + 工作负载 | 4 | 16GB | 100GB SSD |
| node-2 | 工作负载 | 8 | 32GB | 200GB SSD |
| node-3 | 工作负载 | 8 | 32GB | 200GB SSD |

### 8.2 云服务商对比

| 服务商 | 方案 | 3 节点月费(估算) | 托管控制平面 |
|--------|------|-----------------|-------------|
| AWS | EKS | ~$220/月 | 是 (+$73) |
| Azure | AKS | ~$180/月 | 免费 |
| 阿里云 | ACK | ~¥1200/月 | 免费 |
| 自建 | k3s/k0s | ~$80/月(VPS) | 否 |

---

## 九、ConfigMap / Secret 管理

### 9.1 ConfigMap 内容

- 应用配置（YAML/JSON）
- Nginx 配置
- Prometheus 规则
- 环境变量（非敏感）

### 9.2 Secret 内容（K8s Secret + 外部密钥管理）

- 数据库密码 → 外部 Vault / AWS Secrets Manager
- API 密钥
- TLS 证书
- 加密密钥

### 9.3 配置热加载

- ConfigMap 变更通过 Helm 升级
- 支持 `kubectl rollout restart` 触发滚动重启
- 远期规划：集成配置中心（如 Apollo/Nacos）

---

## 十、实施计划

| 阶段 | 任务 | 预计工时 |
|------|------|---------|
| Week 1 | Helm Chart 编写、本地 k3s 验证 | 3 天 |
| Week 1-2 | CI/CD 流水线适配（构建→推送→部署） | 2 天 |
| Week 2 | 云环境部署 + 监控集成 | 3 天 |
| Week 2-3 | HPA 调优、压测验证 | 2 天 |
| Week 3 | 文档完善、上线检查清单 | 2 天 |

---

## 十一、风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| GDAL 依赖在容器中编译失败 | 高 | 中 | 预编译基础镜像层 |
| GPU 节点调度复杂度 | 中 | 低 | 专用节点池 + nodeSelector |
| 持久化存储性能瓶颈 | 高 | 中 | 使用 SSD StorageClass + IOPS 监控 |
| Helm Chart 版本管理混乱 | 中 | 低 | Helm Release + 版本锁定 |
