const { app, BrowserWindow, session } = require('electron')
const path = require('path')

// 优化应用启动性能
app.commandLine.appendSwitch('disable-gpu-vsync');
app.commandLine.appendSwitch('ignore-gpu-blocklist');
app.commandLine.appendSwitch('enable-gpu-rasterization');
app.commandLine.appendSwitch('enable-zero-copy');

function createWindow() {
  const win = new BrowserWindow({
    width: 1400,
    height: 900,
    show: false, // 延迟显示窗口，直到页面加载完成
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      webSecurity: false, // 允许加载本地文件
      backgroundThrottling: false, // 禁用后台节流
      offscreen: false,
      spellcheck: false, // 禁用拼写检查
      plugins: false, // 禁用插件
      webGL: true, // 启用 WebGL
      experimentalFeatures: true, // 启用实验性功能
      preload: path.join(__dirname, '../frontend/dist/preload.js')
    },
    icon: path.join(__dirname, '../logo/UDAKE.icns'),
    backgroundColor: '#ffffff', // 设置背景色，减少闪烁
    titleBarStyle: 'hiddenInset', // macOS 风格标题栏
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