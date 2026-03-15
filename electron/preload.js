/**
 * Electron Preload Script
 * 在渲染进程加载之前执行，提供安全的 IPC 通信接口
 */

const { contextBridge, ipcRenderer } = require('electron')

// 安全地暴露 API 到渲染进程
contextBridge.exposeInMainWorld('electronAPI', {
  // 获取后端端口
  getBackendPort: () => ipcRenderer.invoke('get-backend-port'),
  
  // 系统信息
  platform: process.platform,
  version: process.versions.electron,
  
  // 通信方法
  send: (channel, ...args) => ipcRenderer.send(channel, ...args),
  invoke: (channel, ...args) => ipcRenderer.invoke(channel, ...args),
  on: (channel, callback) => ipcRenderer.on(channel, (event, ...args) => callback(...args)),
  once: (channel, callback) => ipcRenderer.once(channel, (event, ...args) => callback(...args)),
  removeListener: (channel, callback) => ipcRenderer.removeListener(channel, callback),
})

// 暴露常用工具函数
contextBridge.exposeInMainWorld('electronUtils', {
  // 打开外部链接
  openExternal: (url) => ipcRenderer.invoke('open-external', url),
  
  // 显示文件对话框
  showOpenDialog: (options) => ipcRenderer.invoke('show-open-dialog', options),
  
  // 显示保存对话框
  showSaveDialog: (options) => ipcRenderer.invoke('show-save-dialog', options),
  
  // 获取应用版本
  getVersion: () => ipcRenderer.invoke('get-app-version'),
})