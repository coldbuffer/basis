#!/usr/bin/env node
/**
 * Desktop dev: spawn Basis API (desktop profile) + Vite (desktop mode) + Electron.
 */
import { createRequire } from 'node:module';
import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);

import { REPO_ROOT, spawnBasisApi, waitForHttp } from '../electron/server-manager.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const desktopRoot = path.resolve(__dirname, '..');
const webRoot = path.join(REPO_ROOT, 'web');

const WEB_HOST = '127.0.0.1';
/** Fellow desktop renderer HMR uses 3002 (not server dev 5173). */
const WEB_PORT = process.env.BASIS_DESKTOP_WEB_PORT ?? '3002';
const webUrl = `http://${WEB_HOST}:${WEB_PORT}`;

const children = [];

function track(child, label) {
  children.push({ child, label });
  child.on('exit', (code, signal) => {
    if (signal) console.log(`[${label}] exited (${signal})`);
    else if (code !== 0 && code !== null) console.error(`[${label}] exited with code ${code}`);
  });
}

function shutdown() {
  for (const { child, label } of children) {
    try {
      child.kill('SIGTERM');
    } catch {
      console.warn(`[${label}] kill failed`);
    }
  }
}

process.on('SIGINT', () => {
  shutdown();
  process.exit(0);
});
process.on('SIGTERM', () => {
  shutdown();
  process.exit(0);
});

async function main() {
  console.log(
    '[desktop] Starting Basis API (profile=desktop)… first start can take 1–2 min while Python loads.',
  );
  const { child: apiChild, apiBase } = await spawnBasisApi();
  track(apiChild, 'basis-api');
  console.log(`[desktop] API ready at ${apiBase}`);

  console.log('[desktop] Starting Vite (mode=desktop)…');
  const vite = spawn('npm', ['run', 'dev:desktop'], {
    cwd: webRoot,
    env: { ...process.env, VITE_BASIS_API_URL: apiBase },
    stdio: 'inherit',
    shell: true,
  });
  track(vite, 'vite');

  await waitForHttp(webUrl);
  console.log(`[desktop] Web ready at ${webUrl}`);

  const electronEnv = {
    ...process.env,
    BASIS_DESKTOP_API_BASE: apiBase,
    BASIS_DESKTOP_WEB_URL: webUrl,
  };
  const electronBin = require('electron');
  const electron = spawn(electronBin, [desktopRoot], {
    env: { ...electronEnv, BASIS_DESKTOP_BOOTSTRAP: '0' },
    stdio: 'inherit',
  });
  track(electron, 'electron');

  electron.on('exit', () => {
    shutdown();
    process.exit(0);
  });
}

main().catch((err) => {
  console.error(err);
  shutdown();
  process.exit(1);
});
