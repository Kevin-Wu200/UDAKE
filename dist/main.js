const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');
const net = require('net');

let mainWindow;
let backendProcess;
let backendPort = 18081;

// 日志文件路径
const logDir = path.join(app.getPath('userData'), 'logs');
const logFile = path.join(logDir, 'app.log');

// 确保日志目录存在
if (!fs.existsSync(logDir)) {
  fs.mkdirSync(logDir, { recursive: true });
}

// 日志函数
function log(message) {
  const timestamp = new Date().toISOString();
  const logMessage = `[${timestamp}] ${message}\n`;
  console.log(logMessage.trim());
  fs.appendFileSync(logFile, logMessage);
}

// 检查端口是否可用
function isPortAvailable(port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once('error', () => resolve(false));
    server.once('listening', () => {
      server.close();
      resolve(true);
    });
    server.listen(port, '127.0.0.1');
  });
}

// 查找可用端口
async function findAvailablePort(startPort) {
  let port = startPort;
  while (port < startPort + 100) {
    if (await isPortAvailable(port)) {
      return port;
    }
    port++;
  }
  throw new Error('无法找到可用端口');
}

// 启动后端服务
async function startBackend() {
  try {
    // 查找可用端口
    backendPort = await findAvailablePort(18081);
    log(`使用端口: ${backendPort}`);

    // 确定后端路径
    const isDev = !app.isPackaged;
    let backendPath;
    let pythonPath;

    if (isDev) {
      // 开发模式
      backendPath = path.join(__dirname, '..', 'backend');
      pythonPath = 'python3';
    } else {
      // 生产模式
      backendPath = path.join(process.resourcesPath, 'backend');
      pythonPath = 'python3';
    }

    log(`后端路径: ${backendPath}`);
    log(`Python路径: ${pythonPath}`);

    // 启动 uvicorn
    const env = {
      ...process.env,
      PORT: backendPort.toString(),
      HOST: '127.0.0.1',
      PYTHONPATH: backendPath
    };

    backendProcess = spawn(
      pythonPath,
      [
        '-m', 'uvicorn',
        'app.main:app',
        '--host', '127.0.0.1',
        '--port', backendPort.toString(),
        '--log-level', 'info'
      ],
      {
        cwd: backendPath,
        env: env,
        stdio: ['ignore', 'pipe', 'pipe'],
        windowsHide: true
      }
    );

    backendProcess.stdout.on('data', (data) => {
      log(`[Backend] ${data.toString().trim()}`);
    });

    backendProcess.stderr.on('data', (data) => {
      log(`[Backend Error] ${data.toString().trim()}`);
    });

    backendProcess.on('error', (error) => {
      log(`[Backend Process Error] ${error.message}`);
    });

    backendProcess.on('exit', (code, signal) => {
      log(`[Backend] 进程退出 code=${code} signal=${signal}`);
    });

    // 等待后端启动
    await waitForBackend(backendPort);
    log('后端服务启动成功');

  } catch (error) {
    log(`启动后端失败: ${error.message}`);
    throw error;
  }
}

// 等待后端服务就绪
function waitForBackend(port, maxAttempts = 30) {
  return new Promise((resolve, reject) => {
    let attempts = 0;
    const checkInterval = setInterval(async () => {
      attempts++;
      if (attempts > maxAttempts) {
        clearInterval(checkInterval);
        reject(new Error('后端启动超时'));
        return;
      }

      try {
        const available = await isPortAvailable(port);
        if (!available) {
          // 端口被占用，说明服务已启动
          clearInterval(checkInterval);
          resolve();
        }
      } catch (error) {
        // 继续等待
      }
    }, 1000);
  });
}

// 创建主窗口
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1200,
    minHeight: 800,
    backgroundColor: '#0B0B0C',
    titleBarStyle: 'hiddenInset',
    trafficLightPosition: { x: 16, y: 16 },
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: false,
      webSecurity: false, // 允许加载外部资源（高德地图 API）
      // preload: path.join(__dirname, 'preload.js')
    },
    show: false
  });

  // 窗口准备好后显示
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  // 加载前端
  const isDev = !app.isPackaged;
  if (isDev) {
    mainWindow.loadFile(path.join(__dirname, '..', 'frontend', 'index.html'));
    // mainWindow.loadURL("http://localhost:5173");
  } else {
    mainWindow.loadFile(path.join(process.resourcesPath, 'frontend', 'index.html'));
    // mainWindow.loadURL("http://localhost:5173");
  }

  // 开发工具
  if (isDev) {
    mainWindow.webContents.openDevTools();
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// 禁止多实例
const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
  log('应用已在运行，退出');
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  app.whenReady().then(async () => {
    try {
      log('应用启动');
      await startBackend();
      createWindow();
    } catch (error) {
      log(`启动失败: ${error.message}`);
      app.quit();
    }
  });
}

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

app.on('before-quit', () => {
  log('应用退出');
  if (backendProcess) {
    log('终止后端进程');
    backendProcess.kill('SIGTERM');
  }
});

// IPC 通信
ipcMain.handle('get-backend-port', () => {
  return backendPort;
});
