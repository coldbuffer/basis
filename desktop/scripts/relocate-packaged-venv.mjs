import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

import {
  bundledPyvenvHome,
  bundledRuntimeMarker,
  cpythonTreeFromPyvenvHome,
  venvPythonBin,
  venvScriptDir,
} from './python-layout.mjs';

function readPyvenvHomeBin(venvDir) {
  const cfgPath = path.join(venvDir, 'pyvenv.cfg');
  const cfg = fs.readFileSync(cfgPath, 'utf8');
  const m = cfg.match(/^home\s*=\s*(.+)\s*$/m);
  if (!m) throw new Error(`[relocate-venv] missing home in ${cfgPath}`);
  return m[1].trim();
}

function writePyvenvHome(venvDir, homeBin) {
  const cfgPath = path.join(venvDir, 'pyvenv.cfg');
  let cfg = fs.readFileSync(cfgPath, 'utf8');
  if (/^home\s*=/m.test(cfg)) {
    cfg = cfg.replace(/^home\s*=.*/m, `home = ${homeBin}`);
  } else {
    cfg = `home = ${homeBin}\n${cfg}`;
  }
  fs.writeFileSync(cfgPath, cfg, 'utf8');
}

function copyDir(src, dest) {
  fs.cpSync(src, dest, { recursive: true, dereference: true, errorOnExist: false });
}

function findVersionedPythonInDir(dir) {
  if (!fs.existsSync(dir)) return null;
  const candidates = fs
    .readdirSync(dir)
    .filter((n) => /^python3(\.\d+)?$/.test(n) && !n.endsWith('-config'))
    .sort()
    .reverse();
  for (const name of candidates) {
    const full = path.join(dir, name);
    const lst = fs.lstatSync(full);
    if (lst.isFile() && !lst.isSymbolicLink()) return full;
  }
  return null;
}

function materializeDanglingPythonLink(linkPath, name) {
  if (!/^python(3)?$/.test(name) && !/^python3\.\d+$/.test(name)) return;
  const fallback = findVersionedPythonInDir(path.dirname(linkPath));
  if (!fallback) return;
  fs.rmSync(linkPath, { recursive: true, force: true });
  fs.copyFileSync(fallback, linkPath);
  try {
    fs.chmodSync(linkPath, 0o755);
  } catch {
    // ignore
  }
}

/**
 * Replace symlink entries with real files/dirs (packaged app must not point off-bundle).
 */
export function materializeCopiedTree(root) {
  if (!fs.existsSync(root)) return;
  for (const name of fs.readdirSync(root)) {
    const full = path.join(root, name);
    const lst = fs.lstatSync(full);
    if (!lst.isSymbolicLink()) {
      if (lst.isDirectory()) materializeCopiedTree(full);
      continue;
    }
    const target = fs.readlinkSync(full);
    const resolved = path.resolve(path.dirname(full), target);
    fs.rmSync(full, { recursive: true, force: true });
    if (!fs.existsSync(resolved)) {
      materializeDanglingPythonLink(full, name);
      continue;
    }
    const rstat = fs.statSync(resolved);
    if (rstat.isDirectory()) {
      fs.cpSync(resolved, full, { recursive: true, dereference: true });
      materializeCopiedTree(full);
    } else {
      fs.copyFileSync(resolved, full);
      try {
        fs.chmodSync(full, 0o755);
      } catch {
        // ignore
      }
    }
  }
}

/** @param {string} dir Directory that may contain python.exe / python3.exe */
export function normalizeWindowsPython3Launcher(dir) {
  const py = path.join(dir, 'python.exe');
  const py3 = path.join(dir, 'python3.exe');
  if (!fs.existsSync(py3)) return;
  const lst = fs.lstatSync(py3);
  if (lst.isFile() && !lst.isSymbolicLink()) return;
  fs.rmSync(py3, { recursive: true, force: true });
  if (fs.existsSync(py)) {
    fs.copyFileSync(py, py3);
  }
}

/** Materialize bundled CPython + venv launchers (mac/win CI paths must not leak into the app). */
export function finalizeBundledSidecar(sidecarRoot) {
  const cpython = path.join(sidecarRoot, 'runtime', 'cpython');
  if (fs.existsSync(cpython)) {
    materializeCopiedTree(cpython);
    if (process.platform === 'win32') normalizeWindowsPython3Launcher(cpython);
  }
  const scriptDir =
    process.platform === 'win32'
      ? path.join(sidecarRoot, 'venv', 'Scripts')
      : path.join(sidecarRoot, 'venv', 'bin');
  if (fs.existsSync(scriptDir)) {
    materializeCopiedTree(scriptDir);
    if (process.platform === 'win32') {
      normalizeWindowsPython3Launcher(scriptDir);
    }
  }
}

/** @deprecated Use finalizeBundledSidecar */
export function finalizeWindowsBundledSidecar(sidecarRoot) {
  finalizeBundledSidecar(sidecarRoot);
}

function bundledCpythonScriptDir(sidecarRoot) {
  const root = path.join(sidecarRoot, 'runtime', 'cpython');
  return process.platform === 'win32' ? root : path.join(root, 'bin');
}

function ensureVenvPythonAliases(binDir, interpreter) {
  if (!fs.existsSync(binDir)) fs.mkdirSync(binDir, { recursive: true });
  const aliases =
    process.platform === 'win32' ? ['python.exe', 'python3.exe'] : ['python3', 'python'];
  for (const alias of aliases) {
    const aliasPath = path.join(binDir, alias);
    if (fs.existsSync(aliasPath) && !fs.lstatSync(aliasPath).isSymbolicLink()) continue;
    fs.rmSync(aliasPath, { recursive: true, force: true });
    fs.copyFileSync(interpreter, aliasPath);
    try {
      fs.chmodSync(aliasPath, 0o755);
    } catch {
      // ignore
    }
  }
}

/** Fail stage when CI picked python.org framework instead of uv-managed CPython. */
export function assertBundledPythonIsPortable(sidecarRoot) {
  if (process.platform !== 'darwin') return;
  const py = findVersionedPythonInDir(bundledCpythonScriptDir(sidecarRoot));
  if (!py) return;
  const otool = spawnSync('otool', ['-L', py], { encoding: 'utf8' });
  if (otool.status !== 0) return;
  if (otool.stdout.includes('Python.framework')) {
    throw new Error(
      '[stage-api] Bundled CPython links to Python.framework (not portable). ' +
        'Use UV_PYTHON_PREFERENCE=only-managed when building the desktop sidecar.',
    );
  }
}

/** Real interpreter inside the venv after symlinks are materialized. */
export function resolvePackagedVenvPython(venvDir) {
  const sidecarRoot = path.dirname(venvDir);
  const binDir = venvScriptDir(venvDir);
  finalizeBundledSidecar(sidecarRoot);
  const fromDir = findVersionedPythonInDir(binDir);
  if (fromDir) return fromDir;
  const fromRuntime = findVersionedPythonInDir(bundledCpythonScriptDir(sidecarRoot));
  if (fromRuntime) {
    ensureVenvPythonAliases(binDir, fromRuntime);
    return fromRuntime;
  }
  const candidate = venvPythonBin(venvDir);
  if (fs.existsSync(candidate)) return candidate;
  throw new Error(`[relocate-venv] missing venv python under ${binDir}`);
}

/**
 * Copy uv-managed CPython tree next to the venv (once, at stage time).
 */
export function stageSidecarPythonRuntime(venvDir, sidecarRoot) {
  const homeFromCfg = readPyvenvHomeBin(venvDir);
  const cpythonRoot = cpythonTreeFromPyvenvHome(homeFromCfg);
  const destRoot = path.join(sidecarRoot, 'runtime', 'cpython');
  if (fs.existsSync(destRoot)) return destRoot;
  console.log('[stage-api] Copying CPython runtime into sidecar…');
  copyDir(cpythonRoot, destRoot);
  finalizeBundledSidecar(sidecarRoot);
  return destRoot;
}

const PACKAGED_PATH_MARKERS = ['/runner/work/', '/Users/runner/'];

/**
 * Fail if the sidecar still references CI monorepo paths (must be finalized at pack time).
 * @param {string} sidecarRoot
 */
export function assertPackagedSidecarPortable(sidecarRoot) {
  const errors = [];
  const pyvenv = path.join(sidecarRoot, 'venv', 'pyvenv.cfg');
  if (fs.existsSync(pyvenv)) {
    const text = fs.readFileSync(pyvenv, 'utf8');
    for (const marker of PACKAGED_PATH_MARKERS) {
      if (text.includes(marker)) {
        errors.push(`pyvenv.cfg references CI path (${marker})`);
        break;
      }
    }
  }
  const venvLib = path.join(sidecarRoot, 'venv', 'lib');
  if (fs.existsSync(venvLib)) {
    for (const pyDir of fs.readdirSync(venvLib)) {
      if (!pyDir.startsWith('python')) continue;
      const site = path.join(venvLib, pyDir, 'site-packages');
      if (!fs.existsSync(site)) continue;
      for (const name of fs.readdirSync(site)) {
        if (name.startsWith('__editable__')) {
          errors.push(`site-packages contains ${name} (use uv sync --no-editable)`);
          break;
        }
      }
    }
  }
  if (errors.length > 0) {
    throw new Error(`[relocate-venv] sidecar not portable:\n${errors.join('\n')}`);
  }
}

/**
 * Finalize bundled sidecar at pack time (stage afterPack). Uses paths relative to the venv
 * so the tree is install-location agnostic; Electron sets PYTHONHOME at launch.
 */
export function finalizePackagedSidecar(venvDir) {
  const sidecarRoot = path.dirname(venvDir);
  finalizeBundledSidecar(sidecarRoot);

  const runtimeHome = bundledPyvenvHome(sidecarRoot);
  const marker = bundledRuntimeMarker(sidecarRoot);
  if (!fs.existsSync(marker)) {
    throw new Error(`[relocate-venv] missing ${marker} — rebuild with --bundle-venv`);
  }
  const venvPython = resolvePackagedVenvPython(venvDir);

  const portableHome = path.relative(venvDir, runtimeHome);
  writePyvenvHome(venvDir, portableHome.split(path.sep).join('/'));

  if (process.platform === 'win32') {
    return;
  }

  const binDir = venvScriptDir(venvDir);
  for (const name of fs.readdirSync(binDir)) {
    const file = path.join(binDir, name);
    let lst;
    try {
      lst = fs.lstatSync(file);
    } catch {
      continue;
    }
    if (!lst.isFile()) continue;
    const buf = fs.readFileSync(file, 'utf8');
    if (!buf.startsWith('#!')) continue;
    const nl = buf.indexOf('\n');
    const first = buf.slice(0, nl);
    if (!first.includes('python')) continue;
    const rest = buf.slice(nl + 1);
    const shebangPython = path.dirname(file) === path.dirname(venvPython)
      ? `./${path.basename(venvPython)}`
      : venvPython;
    fs.writeFileSync(file, `#!${shebangPython}\n${rest}`, 'utf8');
    try {
      fs.chmodSync(file, 0o755);
    } catch {
      // ignore
    }
  }

  assertPackagedSidecarPortable(sidecarRoot);
}

/** @deprecated Use finalizePackagedSidecar */
export const relocatePackagedVenv = finalizePackagedSidecar;
