const { contextBridge, ipcRenderer } = require('electron');

function argValue(flag) {
  const prefix = `--${flag}=`;
  const found = process.argv.find((item) => item.startsWith(prefix));
  return found ? found.slice(prefix.length).trim() : '';
}

function resolveApiBase() {
  const raw = argValue('basis-api-base') || process.env.BASIS_DESKTOP_API_BASE || '';
  return raw.replace(/\/$/, '');
}

const apiBase = resolveApiBase();
const appVersion = argValue('basis-app-version');
const hasCustomWindowControls = process.platform !== 'darwin';

contextBridge.exposeInMainWorld('__BASIS_RUNTIME__', {
  authRequired: false,
  apiBase,
  desktop: true,
  environment: 'local',
  activeTarget: 'local',
  localApiBase: apiBase,
});

contextBridge.exposeInMainWorld('__BASIS_DESKTOP__', {
  apiBase,
  desktop: true,
  authRequired: false,
  hasCustomWindowControls,
  isMac: process.platform === 'darwin',
  windowMinimize: () => {
    ipcRenderer.send('desktop:window-minimize');
  },
  windowMaximize: () => {
    ipcRenderer.send('desktop:window-maximize');
  },
  windowClose: () => {
    ipcRenderer.send('desktop:window-close');
  },
  isWindowMaximized: () => ipcRenderer.invoke('desktop:window-is-maximized'),
  onWindowMaximizedChange: (handler) => {
    const listener = (_event, maximized) => {
      handler(maximized);
    };
    ipcRenderer.on('desktop:window-maximized', listener);
    return () => {
      ipcRenderer.removeListener('desktop:window-maximized', listener);
    };
  },
  appVersion,
  openExternal: (url) => ipcRenderer.invoke('desktop:open-external', url),
});
