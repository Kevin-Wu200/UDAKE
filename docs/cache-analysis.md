# 缓存使用分析

## 前端缓存

### API封装.ts (frontend/js/services/API封装.ts)
- **缓存类型**：Map内存缓存
- **缓存大小**：50项
- **缓存时间**：5分钟 (300000ms)
- **淘汰策略**：简单的LRU（删除最旧的key）
- **问题**：
  - 使用Map.keys().next().value获取最旧的key，这不是真正的LRU，只是删除第一个key
  - 无访问频率统计
  - 缓存命中率无法监控
  - 无持久化支持

### ConfigService.ts (frontend/js/services/ConfigService.ts)
- **缓存类型**：内存缓存
- **缓存时间**：5分钟
- **自动刷新间隔**：10分钟
- **问题**：
  - 无大小限制，可能导致内存泄漏
  - 缓存粒度太粗（整个配置对象）
  - 无访问频率统计

### OfflineManager.ts (frontend/js/utils/OfflineManager.ts)
- **缓存类型**：IndexedDB
- **缓存内容**：离线数据、项目、采样点、结果
- **问题**：
  - 同步逻辑复杂
  - 无过期机制
  - 无缓存大小限制
  - 缓存命中率无法监控

### LocalStorage使用
- **使用位置**：
  - Store.ts - 状态持久化
  - GeofenceManager.ts - 地理围栏数据
  - TrackManager.ts - 轨迹数据
  - PerformanceOptimizer.ts - 性能数据
  - GestureSettingsPanel.ts - 手势设置
  - OnboardingGuide.ts - 引导状态
  - ParameterHistoryManager.ts - 参数历史
  - FeedbackCollector.ts - 反馈数据
  - MapLegend.ts - 图例配置
  - PreferencesPanel.ts - 偏好设置
  - NotificationManager.ts - 通知设置
  - AdvancedFilter.ts - 过滤器设置
  - 其他组件...
- **问题**：
  - 无统一管理
  - 无过期机制
  - 可能过期或冲突
  - 同步存储限制（5-10MB）

### 其他缓存使用
- **PerformanceOptimizer.ts**
  - 位置缓存：cachedLocation
  - 传感器数据缓存：cachedSensorData (最大100项)
  - 问题：无过期机制，手动清理

- **StartupManager.ts**
  - 资源缓存：resourceCache
  - 问题：无过期机制

- **图层管理.ts**
  - 视口缓存：_viewportCache
  - 缓存时间：300ms
  - 问题：缓存时间太短，可能频繁失效

## 后端缓存

### 数据预处理服务.py (backend/app/services/数据预处理服务.py)
- **缓存类型**：内存缓存
- **缓存内容**：空间数据
- **持久化**：保存到文件
- **问题**：
  - 无过期机制
  - 无大小限制，可能导致内存溢出
  - 缓存命中率无法监控

### 其他缓存使用
- **采样点影响评估器.py**
  - 使用functools.lru_cache装饰器
  - 问题：无统计信息

- **配置接口.py**
  - 配置AI缓存开关：AI_CACHE_ENABLED
  - 问题：未实际实现

## 缓存问题总结

### 1. 淘汰策略问题
- 前端API缓存使用伪LRU，不是真正的最近最少使用
- 缺少其他策略：LFU（最不常用）、时间衰减等

### 2. 缓存大小问题
- 多处缓存无大小限制，可能导致内存溢出
- 不同场景需要不同的缓存大小配置

### 3. 过期机制问题
- 大部分缓存无过期机制
- 过期时间不统一，难以管理

### 4. 持久化问题
- 内存缓存无持久化支持
- IndexedDB和LocalStorage缺乏统一管理

### 5. 监控问题
- 缺少缓存命中率监控
- 缺少缓存大小监控
- 缺少性能指标监控

### 6. 一致性问题
- 多层缓存之间缺乏一致性保证
- 缓存更新时缺少失效通知机制

## 优化目标

1. **实现智能缓存策略**
   - 支持多种淘汰策略（LRU、LFU、时间衰减、混合策略）
   - 可配置的缓存大小和TTL
   - 缓存命中率监控

2. **实现双层缓存**
   - 内存缓存：快速访问，容量小
   - 磁盘缓存：慢速访问，容量大
   - 自动提升热门数据到内存

3. **统一缓存管理**
   - 统一的缓存接口
   - 统一的配置管理
   - 统一的监控和统计

4. **持久化支持**
   - 支持缓存持久化到IndexedDB/LocalStorage
   - 支持缓存恢复

5. **缓存预热**
   - 应用启动时预加载热点数据
   - 减少初始加载时间

6. **缓存失效**
   - 支持模式匹配的缓存失效
   - 支持主动刷新

## 预期效果

- API调用减少60%
- 缓存命中率提升到80%以上
- 响应时间减少50%
- 服务器负载降低
- 用户体验提升