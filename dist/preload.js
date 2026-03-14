const { ipcRenderer } = require('electron');

window.electronAPI = {
  getBackendPort: () => ipcRenderer.invoke('get-backend-port'),
  openDownloadFolder: () => ipcRenderer.invoke('open-download-folder'),
  saveFile: (options) => ipcRenderer.invoke('save-file', options)
};
