# 智能不确定性驱动自适应克里金引擎 - 前端架构

## 🆕 地图引擎切换功能

### 支持的地图引擎
- **ArcGIS API for JavaScript** - 功能完整，支持栅格图层
- **天地图 + Leaflet** - 轻量快速，适合开发阶段

### 快速切换
```bash
# 切换到天地图模式
./switch-map-engine.sh tianditu

# 切换到 ArcGIS 模式
./switch-map-engine.sh arcgis

# 查看当前配置
./switch-map-engine.sh status
```

### 相关文档
- 📖 [快速开始指南](../快速开始.md)
- 📖 [地图引擎切换说明](地图引擎切换说明.md)
- 📖 [测试指南](测试指南.md)
- 📖 [测试检查清单](../测试检查清单.md)
- 📖 [实施总结](../实施总结.md)

### 测试工具
- 🧪 [自动化测试页面](test-map-engine.html)
- 🔧 [测试工具类](js/utils/MapEngineTestHelper.js)

## 项目结构

```
/frontend
├── index.html                      # 主页面
├── test-map-engine.html            # 地图引擎测试页面
├── /css                            # 样式文件
│   ├── 主题变量.css                # Apple级设计系统变量
│   ├── 布局样式.css                # 精确布局（px级）
│   ├── 组件样式.css                # 组件样式（按钮、表单等）
│   ├── 动画规范.css                # 60fps动画规范
│   └── 深色模式.css                # 深色模式覆盖
├── /js                             # JavaScript模块
│   ├── 主程序.js                   # 应用主入口
│   ├── 地图初始化.js               # 地图初始化（支持多引擎）
│   ├── 图层管理.js                 # 图层管理器（适配器模式）
│   ├── 任务轮询.js                 # 任务状态轮询
│   ├── /config                     # 配置文件
│   │   ├── map.config.js          # 地图引擎选择配置
│   │   ├── arcgis.config.js       # ArcGIS配置
│   │   └── tianditu.config.js     # 天地图配置
│   ├── /adapters                   # 地图适配器
│   │   ├── MapAdapter.js          # 适配器接口
│   │   ├── ArcGISAdapter.js       # ArcGIS实现
│   │   └── TiandituAdapter.js     # 天地图实现
│   ├── /services                   # 服务层
│   │   └── API封装.js             # 后端API封装
│   └── /utils                      # 工具函数
│       ├── MapEngineTestHelper.js # 地图引擎测试工具
│       ├── coordinateTransformer.js # 坐标转换
│       ├── geojsonParser.js       # GeoJSON解析
│       └── fieldMatcher.js        # 字段匹配
├── /components                     # 可复用组件
└── /assets                         # 静态资源
```

## 设计规范

### 尺寸精确到px
- 顶部导航栏：56px
- 左侧面板：320px
- 面板圆角：20px
- 按钮高度：40px
- 按钮圆角：12px
- 图层控制项高度：36px

### 动画规范
- 60fps流畅
- duration: 200-300ms
- easing: cubic-bezier(0.4, 0.0, 0.2, 1)
- 仅使用transform和opacity

### 色彩系统
- 自动跟随系统：prefers-color-scheme
- 深色模式主背景：#1c1c1e
- 深色模式面板：rgba(44,44,46,0.85)
- 磨砂效果：backdrop-filter: blur(30px)

## 地图引擎配置管理

### 配置文件位置
- 地图引擎选择：`frontend/js/config/map.config.js`
- ArcGIS 配置：`frontend/js/config/arcgis.config.js`
- 天地图配置：`frontend/js/config/tianditu.config.js`
- 后端配置：`backend/app/config.py`

### 配置原则
1. 所有地图参数集中在配置文件
2. 禁止硬编码 API Key 或 Token
3. 支持 Mock 模式（未配置时）
4. 通过配置文件一键切换地图引擎

### 适配器模式
系统采用适配器模式实现地图引擎解耦：
- `MapAdapter` - 统一接口定义
- `ArcGISAdapter` - ArcGIS 实现
- `TiandituAdapter` - 天地图实现

业务代码仅依赖 `MapAdapter` 接口，不依赖具体实现。

### Mock 模式
当 API Key/Token 为占位符时：
- 自动启用 Mock 模式
- 使用公共服务
- 控制台输出警告信息
- 地图功能正常可用

## 后端API交互

### API端点
```
POST /upload-data              # 上传数据
POST /start-kriging            # 启动插值
GET  /task-status/{task_id}    # 查询任务状态
GET  /result/prediction/{task_id}  # 获取预测栅格
GET  /result/variance/{task_id}    # 获取方差栅格
GET  /result/report/{task_id}      # 获取报告
```

### 交互流程
1. 用户上传GeoJSON数据
2. 前端发送POST /start-kriging
3. 返回task_id
4. 每2秒轮询GET /task-status/{task_id}
5. 状态为completed时加载结果
6. 使用ArcGIS ImageryLayer加载栅格

### 错误处理
- 网络错误：显示友好提示
- 跨域处理：CORS配置
- 请求防重复：Map缓存
- 轮询失败重试：最多3次

## 地图功能

### 已实现功能
1. ✅ 支持多地图引擎（ArcGIS、天地图）
2. ✅ 地图引擎一键切换
3. ✅ 加载底图（从配置读取）
4. ✅ 加载采样点（GeoJSON）
5. ✅ 加载预测栅格图层
6. ✅ 加载方差栅格图层
7. ✅ 图层开关控制
8. ✅ 点击地图查询信息
9. ✅ 任务进度条显示
10. ✅ 自动跟随系统深浅模式（ArcGIS）
11. ✅ 坐标系统转换
12. ✅ 适配器模式架构

### 待实现功能
- 栅格图层插件集成（天地图模式）
- 动态色带控制
- 高不确定性区域高亮
- 不确定性指数图层
- 图层透明度滑块
- 深色模式支持（天地图）

## 技术栈
- **地图引擎**
  - ArcGIS API for JavaScript 4.28
  - Leaflet 1.9.4 + 天地图
- **前端技术**
  - 原生 ES6 模块
  - CSS 变量系统
  - Fetch API
  - 无第三方框架依赖
- **设计模式**
  - 适配器模式（地图引擎）
  - 模块化架构
  - 配置驱动
