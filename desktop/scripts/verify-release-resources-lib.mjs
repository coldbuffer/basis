import fs from 'node:fs';
import path from 'node:path';

import { bundledRuntimeMarker, venvBasisBin } from './python-layout.mjs';

/**
 * @param {{ webDistDir: string; profilesDir: string; apiStageDir: string }} roots
 * @returns {string[]} error messages (empty = OK)
 */
export function collectReleaseResourceErrors({ webDistDir, profilesDir, apiStageDir }) {
  const errors = [];

  function missing(label, filePath) {
    if (!fs.existsSync(filePath)) {
      errors.push(`missing ${label}: ${filePath}`);
    }
  }

  missing('web build', path.join(webDistDir, 'index.html'));
  missing('desktop profile', path.join(profilesDir, 'profile.desktop.yaml'));

  const manifestPath = path.join(apiStageDir, 'api-manifest.json');
  missing('api manifest', manifestPath);
  if (!fs.existsSync(manifestPath)) {
    return errors;
  }

  let manifest;
  try {
    manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  } catch (err) {
    errors.push(`invalid api manifest JSON: ${err instanceof Error ? err.message : String(err)}`);
    return errors;
  }

  if (manifest.kind === 'bundled-venv') {
    const sidecarRoot = path.join(apiStageDir, 'sidecar');
    const venvDir = path.join(sidecarRoot, 'venv');
    missing('bundled basis CLI', venvBasisBin(venvDir));
    missing('bundled CPython runtime', bundledRuntimeMarker(sidecarRoot));
    const site = path.join(venvDir, 'lib', 'python3.12', 'site-packages');
    if (fs.existsSync(site)) {
      for (const name of fs.readdirSync(site)) {
        if (name.startsWith('__editable__.basis') || name.startsWith('__editable___basis')) {
          errors.push(
            `bundled venv must use uv sync --no-editable (found ${name} in site-packages)`,
          );
          break;
        }
      }
    }
  } else if (manifest.kind === 'uv-monorepo') {
    missing('monorepo-root.json', path.join(apiStageDir, 'monorepo-root.json'));
  } else {
    errors.push(`unknown api-manifest kind: ${manifest.kind}`);
  }

  return errors;
}

/**
 * @param {{ webDistDir: string; profilesDir: string; apiStageDir: string }} roots
 */
export function verifyReleaseResources(roots) {
  const errors = collectReleaseResourceErrors(roots);
  if (errors.length > 0) {
    throw new Error(errors.join('\n'));
  }
}
