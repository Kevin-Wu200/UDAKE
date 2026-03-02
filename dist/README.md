# UDAKE macOS 应用打包

这个目录包含将 UDAKE 打包为 macOS 原生应用所需的所有文件。

## 快速开始

### 1. 检查环境

```bash
bash dist/scripts/check_env.sh
```

### 2. 构建应用

```bash
bash dist/scripts/build_macos.sh
```

构建完成后，应用位于 `dist/release/UDAKE.app`

### 3. 运行应用

```bash
open dist/release/UDAKE.app
```

## 开发模式

在开发过程中，可以使用开发模式快速测试：

```bash
bash dist/scripts/dev.sh
```

## 目录说明

- `scripts/` - 构建和开发脚本
- `config/` - 应用配置文件
- `build/` - 构建中间文件（自动生成）
- `release/` - 最终应用产物（自动生成）
- `logs/` - 构建日志（自动生成）
- `tmp/` - 临时文件（自动生成）

## 详细文档

完整的构建、调试、签名和发布文档，请查看：

[README_build.md](./README_build.md)

## 技术栈

- **Electron** - 跨平台桌面应用框架
- **FastAPI** - Python 后端服务
- **ArcGIS API for JavaScript** - 地图可视化

## 应用特性

- ✅ 自动启动后端服务
- ✅ 智能端口管理（自动查找可用端口）
- ✅ 支持 macOS 深色模式
- ✅ 单实例运行
- ✅ 支持 Apple Silicon 和 Intel
- ✅ 最低系统要求：macOS 12.0

## 注意事项

1. 所有打包相关文件必须在 `dist/` 目录内
2. 不要在项目根目录创建其他打包目录
3. 图标源文件：`.claude/logo.png`
4. 构建产物会被 git 忽略（已配置 .gitignore）
