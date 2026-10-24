#!/usr/bin/env node
/**
 * Verify API runtime prerequisites and write pack/api-manifest.json (Fellow stage-gateway analogue).
 * Release default: bundle venv into `.api-stage/sidecar` (Fellow `stage:gateway`).
 * Fast local pack: `--uv-monorepo` (needs checkout + `uv` at runtime).
 */
import { execFileSync, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  assertBundledPythonIsPortable,
  finalizePackagedSidecar,
  stageSidecarPythonRuntime,
} from './relocate-packaged-venv.mjs';
import { bundledSidecarChildEnv, findPackagedVenvPython } from '../electron/bundled-sidecar-launch.mjs';
import { venvBasisBin } from './python-layout.mjs';
import { apiStageDir, desktopRoot, repoRoot } from './paths.mjs';

const filePath = fileURLToPath(import.meta.url);
const __dirname = path.dirname(filePath);

function commandVersion(cmd, args) {
  const r = spawnSync(cmd, args, { encoding: 'utf8' });
  if (r.status !== 0) return null;
  return (r.stdout || r.stderr || '').trim().split('\n')[0] ?? null;
}

function rmrf(dir) {
  fs.rmSync(dir, { recursive: true, force: true });
}

/**
 * Create `.api-stage/sidecar/venv` with `uv sync`.
 */
export function bundleSidecarVenv({ repoRoot: root, packDir }) {
  const sidecarRoot = path.join(packDir, 'sidecar');
  const venvDir = path.join(sidecarRoot, 'venv');
  console.log('[stage-api] Bundling Python sidecar (uv venv + sync)…');
  rmrf(sidecarRoot);
  fs.mkdirSync(sidecarRoot, { recursive: true });
  const uvEnv = {
    ...process.env,
    UV_PYTHON_PREFERENCE: 'only-managed',
    UV_PROJECT_ENVIRONMENT: venvDir,
  };
  execFileSync('uv', ['venv', venvDir, '--python', '3.12'], { cwd: root, env: uvEnv, stdio: 'inherit' });
  execFileSync(
    'uv',
    ['sync', '--no-editable', '--extra', 'dev', '--extra', 'explorer', '--directory', root],
    {
      cwd: root,
      env: uvEnv,
      stdio: 'inherit',
    },
  );
  const basisBin = venvBasisBin(venvDir);
  if (!fs.existsSync(basisBin)) {
    throw new Error(`[stage-api] Missing ${basisBin} after uv sync`);
  }
  stageSidecarPythonRuntime(venvDir, sidecarRoot);
  assertBundledPythonIsPortable(sidecarRoot);
  finalizePackagedSidecar(venvDir);

  const python = findPackagedVenvPython(packDir);
  const profilePath = path.join(packDir, 'profiles', 'profile.desktop.yaml');
  const smoke = spawnSync(python, ['-m', 'basis.cli', 'serve', '--help'], {
    encoding: 'utf8',
    cwd: packDir,
    env: {
      ...process.env,
      ...bundledSidecarChildEnv(packDir),
      BASIS_PROFILE_PATH: profilePath,
      BASIS_DEPLOYMENT_PROFILE: 'desktop',
      BASIS_PROFILE: '',
    },
  });
  if (smoke.status !== 0) {
    throw new Error('[stage-api] bundled `basis --help` failed');
  }
  const basisRelative = path.relative(packDir, basisBin).split(path.sep).join('/');
  return { venvDir, basisRelative, basisBin };
}

/**
 * @param {{ repoRoot?: string; packDir?: string; sync?: boolean; bundleVenv?: boolean }} opts
 */
export function stageApi(opts = {}) {
  const root = opts.repoRoot ?? repoRoot;
  const packDir = opts.packDir ?? apiStageDir;
  const runSync = opts.sync !== false;
  const bundleVenv = opts.bundleVenv !== false;

  const uvVersion = commandVersion('uv', ['--version']);
  if (!uvVersion) {
    throw new Error(
      '[stage-api] `uv` not found on PATH. Install https://docs.astral.sh/uv/ before dist or dev desktop.',
    );
  }

  if (!fs.existsSync(path.join(root, 'pyproject.toml'))) {
    throw new Error(`[stage-api] Not a Basis repo: missing ${path.join(root, 'pyproject.toml')}`);
  }

  if (bundleVenv) {
    rmrf(packDir);
  } else {
    rmrf(path.join(packDir, 'sidecar'));
  }
  fs.mkdirSync(packDir, { recursive: true });

  if (runSync && !bundleVenv) {
    console.log('[stage-api] uv sync --extra dev …');
    const sync = spawnSync('uv', ['sync', '--extra', 'dev', '--extra', 'explorer'], {
      cwd: root,
      env: process.env,
      stdio: 'inherit',
    });
    if (sync.status !== 0) {
      throw new Error('[stage-api] uv sync failed');
    }
  }

  let manifest;
  if (bundleVenv) {
    const bundled = bundleSidecarVenv({ repoRoot: root, packDir });
    manifest = {
      kind: 'bundled-venv',
      venvRelative: path.relative(packDir, bundled.venvDir),
      basisRelative: bundled.basisRelative,
      uvVersion,
      profile: 'desktop',
      stagedAt: new Date().toISOString(),
      note: 'Packaged app runs bundled basis CLI; data still under ~/.basis',
    };
  } else {
    manifest = {
      kind: 'uv-monorepo',
      repoRoot: root,
      uvVersion,
      profile: 'desktop',
      stagedAt: new Date().toISOString(),
      note: 'Packaged app runs `uv run basis serve` from repoRoot (see monorepo-root.json).',
    };
  }

  fs.writeFileSync(path.join(packDir, 'api-manifest.json'), JSON.stringify(manifest, null, 2), 'utf8');
  if (!bundleVenv) {
    fs.writeFileSync(
      path.join(packDir, 'monorepo-root.json'),
      JSON.stringify({ root }, null, 2),
      'utf8',
    );
  } else {
    const mono = path.join(packDir, 'monorepo-root.json');
    if (fs.existsSync(mono)) fs.rmSync(mono);
  }
  console.log(`[stage-api] Ready: ${packDir} (${manifest.kind})`);
  return manifest;
}

const isMain =
  process.argv[1] &&
  path.resolve(fileURLToPath(import.meta.url)) === path.resolve(process.argv[1]);
if (isMain) {
  try {
    stageApi({ bundleVenv: !process.argv.includes('--uv-monorepo') });
  } catch (err) {
    console.error(err instanceof Error ? err.message : err);
    process.exit(1);
  }
}
