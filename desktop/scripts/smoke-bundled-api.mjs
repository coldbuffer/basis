#!/usr/bin/env node
/**
 * Headless smoke: run bundled API from a built .app and hit /api/v1/health.
 * Usage: node scripts/smoke-bundled-api.mjs [path/to/Basis.app]
 */
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  bundledSidecarChildEnv,
  findPackagedVenvPython,
} from '../electron/bundled-sidecar-launch.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const desktopRoot = path.resolve(__dirname, '..');

function defaultAppPath() {
  const arm = path.join(desktopRoot, 'release', 'mac-arm64', 'Basis.app');
  if (fs.existsSync(arm)) return arm;
  throw new Error('Pass path/to/Basis.app or run npm run dist:mac:unsigned first');
}

function resourcesDir(appPath) {
  if (process.platform === 'darwin') {
    return path.join(appPath, 'Contents', 'Resources');
  }
  return path.join(appPath, 'resources');
}

async function waitForReady(stderrChunks, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const text = stderrChunks.join('');
    const m = text.match(/"listen_port"\s*:\s*(\d+)/) ?? text.match(/"port"\s*:\s*(\d+)/);
    if (m) return Number(m[1]);
    await new Promise((r) => setTimeout(r, 200));
  }
  throw new Error('Timed out waiting for basis.ready');
}

async function main() {
  const appPath = path.resolve(process.argv[2] ?? defaultAppPath());
  const res = resourcesDir(appPath);
  const python = findPackagedVenvPython(res);
  const profilePath = path.join(res, 'profiles', 'profile.desktop.yaml');
  if (!fs.existsSync(profilePath)) {
    throw new Error(`Missing desktop profile: ${profilePath}`);
  }

  const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'basis-smoke-'));
  const env = {
    ...process.env,
    ...bundledSidecarChildEnv(res),
    BASIS_PROFILE_PATH: profilePath,
    BASIS_DEPLOYMENT_PROFILE: 'desktop',
    BASIS_HOST: '127.0.0.1',
    BASIS_PORT: '0',
    BASIS_HOME: dataDir,
    BASIS_DATA_DIR: dataDir,
    BASIS_SQLITE_PATH: path.join(dataDir, 'basis.db'),
    PYTHONUNBUFFERED: '1',
  };
  delete env.BASIS_LISTEN_PORT_RESOLVED;

  const stderrChunks = [];
  const child = spawn(python, ['-m', 'basis.cli', 'serve'], {
    cwd: res,
    env,
    stdio: ['ignore', 'ignore', 'pipe'],
  });
  child.stderr?.on('data', (c) => stderrChunks.push(String(c)));

  try {
    const port = await waitForReady(stderrChunks, 90_000);
    const resHealth = await fetch(`http://127.0.0.1:${port}/api/v1/health`);
    if (!resHealth.ok) throw new Error(`health HTTP ${resHealth.status}`);
    const body = await resHealth.json();
    if (body?.status !== 'ok') throw new Error(`unexpected health: ${JSON.stringify(body)}`);
    console.log(`[smoke-bundled-api] OK port=${port}`, body);
  } finally {
    child.kill('SIGTERM');
    fs.rmSync(dataDir, { recursive: true, force: true });
  }
}

main().catch((err) => {
  console.error(err instanceof Error ? err.message : err);
  process.exit(1);
});
