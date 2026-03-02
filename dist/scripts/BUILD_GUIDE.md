# macOS 应用构建指南

## 构建问题修复

### 问题描述
构建时下载 arm64 版本的 Electron 超时：
```
Get "https://github.com/electron/electron/releases/download/v28.3.3/electron-v28.3.3-darwin-arm64.zip":
dial tcp 20.205.243.166:443: connect: operation timed out
```

### 解决方案

#### 方案 1: 使用代理构建（推荐）

如果你有网络代理（如 Clash、V2Ray 等），使用代理构建脚本：

```bash
# 使用默认代理地址 (http://127.0.0.1:7890)
bash dist/scripts/build_with_proxy.sh

# 或指定自定义代理地址
bash dist/scripts/build_with_proxy.sh http://127.0.0.1:1087
```

#### 方案 2: 只构建 x64 版本

如果不需要 Apple Silicon (M1/M2) 支持，可以只构建 x64 版本：

1. 编辑 `dist/package.json`
2. 修改 `build.mac.target` 配置：
```json
"target": [
  {
    "target": "default",
    "arch": ["x64"]
  }
]
```
3. 运行构建：
```bash
bash dist/scripts/build_macos.sh
```

#### 方案 3: 使用国内镜像

在构建前设置 Electron 镜像：

```bash
export ELECTRON_MIRROR="https://npmmirror.com/mirrors/electron/"
bash dist/scripts/build_macos.sh
```

## 构建脚本说明

### build_macos.sh
标准构建脚本，构建 x64 + arm64 通用版本。

### build_with_proxy.sh
带代理的构建脚本，自动配置代理环境变量。

**使用方法：**
```bash
# 使用默认代理
bash dist/scripts/build_with_proxy.sh

# 指定代理地址
bash dist/scripts/build_with_proxy.sh http://your-proxy:port
```

**功能：**
- 自动设置 HTTP/HTTPS 代理
- 配置 npm 代理
- 使用淘宝 Electron 镜像
- 构建完成后自动清理代理配置

## 常见代理端口

- Clash: `http://127.0.0.1:7890`
- V2Ray: `http://127.0.0.1:1087`
- Shadowsocks: `http://127.0.0.1:1080`

## 构建产物

构建成功后，产物位于 `dist/release/` 目录：
- `UDAKE.app` - macOS 应用程序
- `UDAKE-1.0.0.dmg` - DMG 安装包
- `UDAKE-1.0.0-mac.zip` - ZIP 压缩包
- `build_info.json` - 构建信息

## 运行应用

```bash
open dist/release/UDAKE.app
```

或直接双击 `UDAKE.app` 启动。
