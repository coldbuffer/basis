import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { resolveBundledSidecarLaunch } from './bundled-sidecar-launch.mjs';
import { loadPackagedApiManifest } from './api-manifest.mjs';
import { isPackagedApp } from './paths.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
export const REPO_ROOT = path.resolve(__dirname, '../..');

const READY_EVENTS = new Set(['basis.ready', 'gateway.ready']);

function resolveLaunch(opts) {
  const manifest = opts.apiManifest ?? loadPackagedApiManifest(opts.resourcesPath);
  if (manifest?.kind === 'bundled-venv' && opts.resourcesPath) {
    const launch = resolveBundledSidecarLaunch(opts.resourcesPath);
    return { ...launch, bundled: true, sidecarEnv: launch.env };
  }

  const repoRoot = opts.repoRoot ?? REPO_ROOT;
  const uvCheck = spawnSync('uv', ['--version'], { encoding: 'utf8' });
  if (uvCheck.status !== 0) {
    throw new Error(
      '`uv` is not on PATH. Install uv (https://docs.astral.sh/uv/) or rebuild with `npm run dist:mac:unsigned` (bundled Python).',
    );
  }
  return {
    cmd: 'uv',
    args: ['run', 'basis', 'serve', '--profile', 'desktop'],
    cwd: repoRoot,
    bundled: false,
  };
}

/**
 * @param {{
 *   repoRoot?: string;
 *   resourcesPath?: string;
 *   apiManifest?: Record<string, unknown>;
 *   dataDir?: string;
 *   profilePath?: string;
 *   port?: number | string;
 * }} opts
 */
export async function spawnBasisApi(opts = {}) {
  const repoRoot = opts.repoRoot ?? REPO_ROOT;
  const profilePath =
    opts.profilePath ?? path.join(repoRoot, 'profiles', 'profile.desktop.yaml');
  const dataDir = opts.dataDir ?? path.join(os.homedir(), '.basis');
  const home = dataDir;

  if (!fs.existsSync(profilePath)) {
    throw new Error(`Desktop profile not found: ${profilePath}`);
  }

  const launch = resolveLaunch(opts);

  const env = { ...process.env };
  // Desktop always uses profile `server.port: 0` (OS-assigned). Ignore repo `.env` BASIS_PORT=8090.
  delete env.BASIS_LISTEN_PORT_RESOLVED;
  delete env.BASIS_PORT;
  Object.assign(env, {
    BASIS_PROFILE_PATH: profilePath,
    BASIS_HOME: home,
    BASIS_DATA_DIR: dataDir,
    BASIS_SQLITE_PATH: path.join(dataDir, 'basis.db'),
    BASIS_DEPLOYMENT_PROFILE: 'desktop',
    BASIS_HOST: '127.0.0.1',
    BASIS_PORT: opts.port !== undefined ? String(opts.port) : '0',
    PYTHONUNBUFFERED: '1',
  });
  if (launch.sidecarEnv) {
    Object.assign(env, launch.sidecarEnv);
    delete env.BASIS_PROFILE;
  }

  const child = spawn(launch.cmd, launch.args, {
    cwd: launch.cwd,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  const logApi = (chunk) => {
    const text = chunk.toString();
    if (process.env.BASIS_DESKTOP_VERBOSE === '1' || isPackagedApp()) {
      process.stderr.write(`[basis-api] ${text}`);
    }
  };
  child.stdout?.on('data', logApi);
  child.stderr?.on('data', logApi);

  const ready = await waitForReadyLine(child, 120_000);
  const apiBase = `http://${ready.host}:${ready.port}`;
  return { child, apiBase, host: ready.host, port: ready.port, profilePath };
}

function waitForReadyLine(child, timeoutMs) {
  return new Promise((resolve, reject) => {
    let settled = false;
    const timer = setTimeout(() => {
      if (!settled) {
        settled = true;
        child.kill('SIGTERM');
        reject(new Error('Timed out waiting for basis.ready / gateway.ready'));
      }
    }, timeoutMs);

    const onData = (chunk) => {
      const text = chunk.toString();
      for (const line of text.split('\n')) {
        const trimmed = line.trim();
        if (!trimmed.includes('ready')) continue;
        try {
          const payload = JSON.parse(trimmed);
          if (READY_EVENTS.has(payload.event)) {
            if (!settled) {
              settled = true;
              clearTimeout(timer);
              resolve({ host: payload.host, port: payload.port });
            }
            return;
          }
        } catch {
          // uvicorn may prefix log lines; try substring JSON
          const start = trimmed.indexOf('{');
          if (start < 0) continue;
          try {
            const payload = JSON.parse(trimmed.slice(start));
            if (READY_EVENTS.has(payload.event) && !settled) {
              settled = true;
              clearTimeout(timer);
              resolve({ host: payload.host, port: payload.port });
            }
          } catch {
            // ignore
          }
        }
      }
    };

    child.stdout?.on('data', onData);
    child.stderr?.on('data', onData);
    child.on('error', (err) => {
      if (!settled) {
        settled = true;
        clearTimeout(timer);
        reject(err);
      }
    });
    child.on('exit', (code) => {
      if (!settled) {
        settled = true;
        clearTimeout(timer);
        reject(new Error(`basis serve exited with code ${code ?? 'unknown'}`));
      }
    });
  });
}

export async function waitForHttp(url, timeoutMs = 60_000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url, { method: 'GET' });
      if (res.ok || res.status === 304) return;
    } catch {
      // retry
    }
    await new Promise((r) => setTimeout(r, 400));
  }
  throw new Error(`Timed out waiting for ${url}`);
}
