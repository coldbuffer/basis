import fs from 'node:fs';
import path from 'node:path';

/** @param {string} resourcesPath App Resources (or .api-stage) root */
export function bundledRuntimeCpythonHome(resourcesPath) {
  return path.join(resourcesPath, 'sidecar', 'runtime', 'cpython');
}

/** @param {string} resourcesPath */
export function findPackagedVenvPython(resourcesPath) {
  const binDir =
    process.platform === 'win32'
      ? path.join(resourcesPath, 'sidecar', 'venv', 'Scripts')
      : path.join(resourcesPath, 'sidecar', 'venv', 'bin');
  const names =
    process.platform === 'win32' ? ['python.exe', 'python3.exe'] : ['python3.12', 'python3', 'python'];
  for (const name of names) {
    const candidate = path.join(binDir, name);
    if (!fs.existsSync(candidate)) continue;
    if (fs.statSync(candidate).isFile()) return candidate;
  }
  throw new Error(`[bundled-sidecar] missing venv python under ${binDir}`);
}

/** Env vars for bundled CPython + venv site-packages (no pyvenv.cfg rewrite at launch). */
export function bundledSidecarChildEnv(resourcesPath) {
  return {
    PYTHONHOME: bundledRuntimeCpythonHome(resourcesPath),
  };
}

/** @param {string} resourcesPath */
export function resolveBundledSidecarLaunch(resourcesPath) {
  return {
    cmd: findPackagedVenvPython(resourcesPath),
    args: ['-m', 'basis.cli', 'serve', '--profile', 'desktop'],
    cwd: resourcesPath,
    env: bundledSidecarChildEnv(resourcesPath),
  };
}
