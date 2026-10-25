#!/usr/bin/env node
/**
 * S0: ensure web/src does not embed legacy /api/* URL literals (use /api/v1).
 * Explorer runtime uses `/api/graph/...` suffixes resolved to v1 — excluded.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const webSrc = path.join(repoRoot, 'web', 'src');

const SKIP_FILES = [
  'lib/workspace/ws-http.tsx',
  'lib/workspace/ws-http.test.ts',
  'lib/workspace/ws-client.ts',
];

const files = [];
function walk(dir) {
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name);
    const st = fs.statSync(full);
    if (st.isDirectory()) walk(full);
    else if (/\.(tsx?|mjs)$/.test(name)) files.push(full);
  }
}
walk(webSrc);

const legacyHits = [];

const legacyRe = /['"`](\/api\/(?!v1\/)[^'"`\s]*)/g;

for (const file of files) {
  const rel = path.relative(path.join(repoRoot, 'web', 'src'), file);
  if (SKIP_FILES.some((s) => rel === s || rel.endsWith(s))) continue;
  if (/\.(test|spec)\.(tsx?|mjs)$/.test(rel)) continue;

  const text = fs.readFileSync(file, 'utf8');
  let m;
  while ((m = legacyRe.exec(text))) {
    const p = m[1];
    if (p === '/api/v1') continue;
    if (p.startsWith('/api/graph/')) continue;
    legacyHits.push({ file: path.relative(repoRoot, file), path: p });
  }
}

if (legacyHits.length) {
  console.error('Legacy /api/* string literals in web/src (use /api/v1):');
  for (const hit of legacyHits) {
    console.error(`  ${hit.file}: ${hit.path}`);
  }
  process.exit(1);
}

console.log(`OK: ${files.length} files scanned; no legacy /api/* literals.`);
