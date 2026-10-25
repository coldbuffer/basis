#!/usr/bin/env node
/**
 * Regenerate web OpenAPI TypeScript types from openapi/basis-v1.json.
 *
 * Usage: node scripts/openapi/gen-client-types.mjs
 */
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const webDir = path.join(repoRoot, 'web');

const npm = process.platform === 'win32' ? 'npm.cmd' : 'npm';
const result = spawnSync(npm, ['run', 'gen:openapi-types'], {
  cwd: webDir,
  stdio: 'inherit',
});

if (result.status !== 0) {
  process.exit(result.status ?? 1);
}

console.log('Wrote web/src/lib/openapi/schema.d.ts (+ schema-workspaces.d.ts)');
