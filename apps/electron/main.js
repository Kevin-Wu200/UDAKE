const { app, BrowserWindow, session, ipcMain, shell } = require('electron')
const path = require('path')

function stripTrailingSlash(value) {
  return String(value || '').replace(/\/+$/, '');
}

function resolveBackendHost() {
  return process.env.IPCONFIG || process.env.VITE_IPCONFIG || process.env.VITE_BACKEND_HOST || 'localhost';
}

function resolveBackendPort() {
  return process.env.BACKEND_PORT || process.env.VITE_BACKEND_PORT || '8000';
}

function resolveBackendUrl() {
  const fallback = `http://${resolveBackendHost()}:${resolveBackendPort()}`;
  const configured = process.env.BACKEND_URL || process.env.VITE_API_BASE_URL || process.env.VITE_API_URL || fallback;
  return stripTrailingSlash(configured).replace(/\/api$/, '');
}

function resolveWsUrl(backendUrl) {
  const configured = process.env.WS_URL || process.env.VITE_WS_URL;
  if (configured) {
    return stripTrailingSlash(configured);
  }
  return backendUrl.replace(/^http/i, 'ws');
}

// 优化应用启动性能
app.commandLine.appendSwitch('disable-gpu-vsync');
app.commandLine.appendSwitch('ignore-gpu-blocklist');
app.commandLine.appendSwitch('enable-gpu-rasterization');
app.commandLine.appendSwitch('enable-zero-copy');

// IPC 处理程序
ipcMain.handle('get-backend-port', () => {
  return Number(resolveBackendPort()) // 后端默认端口
})

ipcMain.handle('open-external', async (event, url) => {
  await shell.openExternal(url)
})

ipcMain.handle('show-open-dialog', async (event, options) => {
  // 实现文件选择对话框
  return { canceled: true, filePaths: [] }
})

ipcMain.handle('show-save-dialog', async (event, options) => {
  // 实现保存文件对话框
  return { canceled: true, filePath: '' }
})

ipcMain.handle('get-app-version', () => {
  return app.getVersion()
})

function createWindow() {
  const backendUrl = resolveBackendUrl();
  const wsUrl = resolveWsUrl(backendUrl);
  const cspConnectSrc = ["'self'", backendUrl, wsUrl, 'https:', 'wss:', 'blob:', 'https://*.amap.com'].join(' ');

  const win = new BrowserWindow({
    width: 1400,
    height: 900,
    show: false, // 延迟显示窗口，直到页面加载完成
    webPreferences: {
      nodeIntegration: false, // 禁用 nodeIntegration，提高安全性
      contextIsolation: true, // 启用上下文隔离，提高安全性
      webSecurity: true, // 启用 webSecurity，提高安全性
      backgroundThrottling: false, // 禁用后台节流
      offscreen: false,
      spellcheck: false, // 禁用拼写检查
      plugins: false, // 禁用插件
      webGL: true, // 启用 WebGL
      sandbox: true, // 启用沙箱以提高安全性
      allowRunningInsecureContent: true, // 允许加载 HTTP 内容（开发环境）
      webviewTag: true, // 允许使用 webview 标签（支持 iframe）
      preload: path.join(__dirname, 'preload.js')
    },
    icon: path.join(__dirname, '../../logo/UDAKE.icns'),
    backgroundColor: '#ffffff', // 设置背景色，减少闪烁
    titleBarStyle: 'hiddenInset', // macOS 风格标题栏
  })

  // 设置内容安全策略 - 添加高德地图支持
  // 注意：高德地图 SDK 需要 'unsafe-eval' 权限来执行动态代码
  win.webContents.session.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        'Content-Security-Policy': [
          "default-src 'self';",
          "script-src 'self' 'unsafe-inline' 'unsafe-eval' blob: https://js.arcgis.com https://webapi.amap.com https://*.amap.com;",
          "style-src 'self' 'unsafe-inline' blob: https://js.arcgis.com https://webapi.amap.com;",
          "img-src 'self' data: blob: https: https://*.arcgis.com https://*.autonavi.com https://*.amap.com;",
          "font-src 'self' data: blob:;",
          `connect-src ${cspConnectSrc};`,
          "media-src 'self' data: blob:;",
          "object-src 'none';",
          "base-uri 'self';",
          "form-action 'self';",
          "worker-src 'self' blob:;",
          "frame-src 'self' https://*.arcgis.com https://*.amap.com;",
          "frame-ancestors 'self';"
        ].join(' ')
      }
    })
  })

  // 加载构建后的前端
  win.loadFile(path.join(__dirname, '../frontend/dist/index.html'))

  // 页面加载完成后显示窗口
  win.once('ready-to-show', () => {
    win.show()
  })

  // 开发模式下打开 DevTools
  if (process.env.NODE_ENV === 'development') {
    win.webContents.openDevTools()
  }

  // 优化会话配置
  const ses = win.webContents.session
  ses.clearCache() // 清除缓存以获得最佳性能
}

// 应用就绪时创建窗口
app.whenReady().then(() => {
  // 优化应用启动性能
  if (process.platform === 'darwin') {
    app.setAboutPanelOptions({
      applicationName: 'UDAKE',
      applicationVersion: '1.0.0',
      copyright: 'Copyright © 2026'
    })
  }

  createWindow()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow()
  }
})
