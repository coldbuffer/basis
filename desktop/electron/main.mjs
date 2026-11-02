import { app, BrowserWindow, dialog, ipcMain, shell } from 'electron';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { bootstrapDesktopShell, shutdownDesktopShell } from './bootstrap.mjs';
import { isPackagedApp } from './paths.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** In-app window buttons on Windows/Linux — native WCO hover is unreliable. */
const USE_CUSTOM_WINDOW_CONTROLS = process.platform !== 'darwin';

let windowIpcRegistered = false;

/** @type {string | null} */
let webUrl = null;
/** @type {string | null} */
let apiBase = null;

function registerDesktopWindowIpc() {
  if (windowIpcRegistered) return;
  windowIpcRegistered = true;

  ipcMain.on('desktop:window-minimize', (event) => {
    if (!USE_CUSTOM_WINDOW_CONTROLS) return;
    BrowserWindow.fromWebContents(event.sender)?.minimize();
  });

  ipcMain.on('desktop:window-maximize', (event) => {
    if (!USE_CUSTOM_WINDOW_CONTROLS) return;
    const win = BrowserWindow.fromWebContents(event.sender);
    if (!win) return;
    if (win.isMaximized()) win.unmaximize();
    else win.maximize();
  });

  ipcMain.on('desktop:window-close', (event) => {
    if (!USE_CUSTOM_WINDOW_CONTROLS) return;
    BrowserWindow.fromWebContents(event.sender)?.close();
  });

  ipcMain.handle('desktop:window-is-maximized', (event) => {
    return BrowserWindow.fromWebContents(event.sender)?.isMaximized() ?? false;
  });

  ipcMain.handle('desktop:open-external', (_event, url) => {
    if (typeof url !== 'string') return false;
    const trimmed = url.trim();
    if (!/^https?:\/\//i.test(trimmed)) return false;
    return shell.openExternal(trimmed);
  });
}

function attachWindowChromeHandlers(win) {
  if (!USE_CUSTOM_WINDOW_CONTROLS) return;
  const emitMaximized = () => {
    if (win.isDestroyed()) return;
    win.webContents.send('desktop:window-maximized', win.isMaximized());
  };
  win.on('maximize', emitMaximized);
  win.on('unmaximize', emitMaximized);
}

function createWindow() {
  if (!webUrl || !apiBase) return;
  process.env.BASIS_DESKTOP_API_BASE = apiBase;
  process.env.BASIS_DESKTOP_WEB_URL = webUrl;
  registerDesktopWindowIpc();

  const win = new BrowserWindow({
    width: 1280,
    height: 840,
    minWidth: 960,
    minHeight: 640,
    title: 'Basis',
    backgroundColor: '#fafafa',
    // hiddenInset: traffic lights sit slightly lower — matches Fellow mac sidebar header rhythm.
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'hidden',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.mjs'),
      additionalArguments: [`--basis-api-base=${apiBase}`],
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  attachWindowChromeHandlers(win);
  void win.loadURL(webUrl);
}

if (isPackagedApp()) {
  const gotLock = app.requestSingleInstanceLock();
  if (!gotLock) {
    app.quit();
  } else {
    app.on('second-instance', () => {
      const win = BrowserWindow.getAllWindows()[0];
      if (win) {
        if (win.isMinimized()) win.restore();
        win.focus();
      }
    });
  }
}

app.whenReady().then(async () => {
  try {
    if (isPackagedApp() || process.env.BASIS_DESKTOP_BOOTSTRAP === '1') {
      const boot = await bootstrapDesktopShell();
      apiBase = boot.apiBase;
      webUrl = boot.webUrl;
      createWindow();
    } else {
      apiBase = process.env.BASIS_DESKTOP_API_BASE ?? 'http://127.0.0.1:8090';
      webUrl = process.env.BASIS_DESKTOP_WEB_URL ?? 'http://127.0.0.1:3002';
      createWindow();
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error('[basis-desktop]', message);
    dialog.showErrorBox('Basis Desktop', message);
    app.quit();
    return;
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('before-quit', () => {
  shutdownDesktopShell();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
