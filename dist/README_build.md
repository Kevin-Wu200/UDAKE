# UDAKE macOS 应用构建指南

## 📦 构建方法

### 前置要求

1. **Node.js 和 npm**
   ```bash
   node --version  # 需要 v16 或更高
   npm --version
   ```

2. **Python 3**
   ```bash
   python3 --version  # 需要 3.8 或更高
   pip3 --version
   ```

3. **macOS 开发工具**
   ```bash
   xcode-select --install
   ```

### 快速构建

在项目根目录执行：

```bash
bash dist/scripts/build_macos.sh
```

构建完成后，应用位于：

```
dist/release/UDAKE.app
```

### 构建流程说明

构建脚本会自动完成以下步骤：

1. **清理旧构建** - 删除之前的构建产物
2. **构建前端** - 复制前端文件到 `dist/build/frontend`
3. **构建后端** - 复制后端代码到 `dist/build/backend`
4. **生成图标** - 从 `dist/logo.png` 生成 `dist/UDAKE.icns`
5. **安装依赖** - 安装 Electron 和相关依赖
6. **打包应用** - 使用 electron-builder 生成 macOS 应用

---

## 🔧 调试方法

### 开发模式运行

1. 安装依赖：
   ```bash
   cd dist
   npm install
   ```

2. 启动应用：
   ```bash
   npm start
   ```

### 查看日志

应用日志位于：

```
~/Library/Application Support/udake/logs/app.log
```

实时查看日志：

```bash
tail -f ~/Library/Application\ Support/udake/logs/app.log
```

### 调试后端

单独启动后端服务：

```bash
cd backend
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 18081 --reload
```

### 调试前端

在浏览器中打开：

```
file:///Users/你的用户名/UDAKE/frontend/index.html
```

或使用简单的 HTTP 服务器：

```bash
cd frontend
python3 -m http.server 8000
```

然后访问 `http://localhost:8000`

---

## 🚀 Release 方法

### 生成发布版本

1. 确保代码已提交到 git
2. 运行构建脚本：
   ```bash
   bash dist/scripts/build_macos.sh
   ```

3. 测试生成的应用：
   ```bash
   open dist/release/UDAKE.app
   ```

### 版本号管理

修改 `dist/package.json` 中的版本号：

```json
{
  "version": "1.0.0"
}
```

### 构建信息

每次构建会生成 `dist/release/build_info.json`，包含：

- 应用名称
- 版本号
- 构建时间
- 平台信息
- Bundle ID

---

## ✍️ 签名方法

### 开发者证书

1. 在 Apple Developer 账户中创建证书
2. 下载并安装到钥匙串

### 签名应用

```bash
codesign --deep --force --verify --verbose \
  --sign "Developer ID Application: Your Name (TEAM_ID)" \
  dist/release/UDAKE.app
```

### 验证签名

```bash
codesign --verify --deep --strict --verbose=2 dist/release/UDAKE.app
spctl -a -t exec -vv dist/release/UDAKE.app
```

### 公证（Notarization）

1. 创建应用专用密码（App-Specific Password）

2. 上传公证：
   ```bash
   xcrun notarytool submit dist/release/UDAKE.app \
     --apple-id "your@email.com" \
     --password "app-specific-password" \
     --team-id "TEAM_ID" \
     --wait
   ```

3. 装订公证票据：
   ```bash
   xcrun stapler staple dist/release/UDAKE.app
   ```

---

## 💿 DMG 制作方法

### 使用 create-dmg

1. 安装工具：
   ```bash
   brew install create-dmg
   ```

2. 创建 DMG：
   ```bash
   create-dmg \
     --volname "UDAKE" \
     --volicon "dist/UDAKE.icns" \
     --window-pos 200 120 \
     --window-size 800 400 \
     --icon-size 100 \
     --icon "UDAKE.app" 200 190 \
     --hide-extension "UDAKE.app" \
     --app-drop-link 600 185 \
     "dist/release/UDAKE-1.0.0.dmg" \
     "dist/release/UDAKE.app"
   ```

### 手动创建 DMG

1. 创建临时 DMG：
   ```bash
   hdiutil create -size 500m -fs HFS+ -volname "UDAKE" dist/tmp/temp.dmg
   ```

2. 挂载并复制文件：
   ```bash
   hdiutil attach dist/tmp/temp.dmg
   cp -r dist/release/UDAKE.app /Volumes/UDAKE/
   ln -s /Applications /Volumes/UDAKE/Applications
   ```

3. 设置背景和图标位置（使用 Finder）

4. 卸载并转换为压缩格式：
   ```bash
   hdiutil detach /Volumes/UDAKE
   hdiutil convert dist/tmp/temp.dmg -format UDLZO -o dist/release/UDAKE-1.0.0.dmg
   ```

---

## 📁 目录结构

```
dist/
├── build/              # 构建中间文件
│   ├── frontend/       # 前端构建产物
│   └── backend/        # 后端构建产物
├── scripts/            # 构建脚本
│   └── build_macos.sh  # macOS 构建脚本
├── config/             # 配置文件
│   └── entitlements.mac.plist
├── resources/          # 资源文件
├── logs/               # 构建日志
├── tmp/                # 临时文件
├── release/            # 最终产物
│   ├── UDAKE.app       # macOS 应用
│   └── build_info.json # 构建信息
├── package.json        # Electron 配置
├── main.js             # Electron 主进程
├── preload.js          # Electron 预加载脚本
└── UDAKE.icns          # 应用图标
```

---

## ⚙️ 配置说明

### Electron 配置

编辑 `dist/package.json` 中的 `build` 字段：

```json
{
  "build": {
    "appId": "com.udake.kriging",
    "productName": "UDAKE",
    "mac": {
      "category": "public.app-category.developer-tools",
      "minimumSystemVersion": "12.0"
    }
  }
}
```

### 后端端口

默认端口：`18081`

如果端口被占用，应用会自动查找可用端口（18081-18180）

### 深色模式

应用自动支持 macOS 深色模式，配色方案：

- 深色背景：`#0B0B0C`
- 主字体：`#FFFFFF`
- 次级字体：`#B0B0B5`

---

## 🐛 常见问题

### 构建失败

1. 检查 Node.js 和 Python 版本
2. 清理并重新安装依赖：
   ```bash
   cd dist
   rm -rf node_modules package-lock.json
   npm install
   ```

### 应用无法启动

1. 查看日志文件
2. 检查后端依赖是否安装：
   ```bash
   pip3 install -r requirements.txt
   ```

### 图标未显示

1. 确认 `dist/logo.png` 存在
2. 重新生成图标：
   ```bash
   rm dist/UDAKE.icns
   bash dist/scripts/build_macos.sh
   ```

### 端口冲突

应用会自动查找可用端口，如果仍有问题：

1. 检查端口占用：
   ```bash
   lsof -i :18081
   ```

2. 终止占用进程：
   ```bash
   kill -9 <PID>
   ```

---

## 📝 开发注意事项

1. **不要在根目录创建新文件夹** - 所有打包相关文件必须在 `dist/` 内
2. **图标源文件** - 只能使用 `dist/logo.png`
3. **日志位置** - 运行时日志在用户目录,构建日志在 `dist/logs/`
4. **单实例运行** - 应用会阻止多实例启动
5. **自动端口分配** - 后端会自动查找可用端口

---

## 📞 技术支持

如有问题，请查看：

- 应用日志：`~/Library/Application Support/udake/logs/app.log`
- 构建日志：`dist/logs/`
- 项目文档：`README.md`
