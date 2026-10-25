#!/usr/bin/env node
// Regenerate i18n/locales/{en,zh}/pages.ts from module fragments (@/ imports).
// Run: npx tsx scripts/compose-pages-locale.mjs
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const srcRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../src');

const PAGE_BLOCKS = [
  ['alerts', '@/modules/alerts/i18n', 'pages-alerts'],
  ['basisKbs', '@/modules/admin-workspaces/i18n', 'pages-basisKbs'],
  ['basisAudit', '@/modules/admin-audit/i18n', 'pages-basisAudit'],
  ['basisUsers', '@/modules/admin-users/i18n', 'pages-basisUsers'],
  ['swagger', '@/modules/swagger/i18n', 'pages-swagger'],
];

const KB_SUBTITLE_MODULES = [
  ['review', '@/modules/review/i18n'],
  ['search', '@/modules/search/i18n'],
  ['analyze', '@/modules/analyze/i18n'],
  ['entities', '@/modules/entities/i18n'],
  ['sources', '@/modules/library/i18n'],
  ['connectors', '@/modules/connectors/i18n'],
  ['processing', '@/modules/processing/i18n'],
  ['graphDiff', '@/modules/graph/i18n'],
  ['alerts', '@/modules/alerts/i18n'],
  ['settings', '@/modules/settings/i18n'],
];

function writePages(lang) {
  const lines = [];
  lines.push('/** Composed from module page fragments. */');
  lines.push('');
  for (const [exportName, base, file] of PAGE_BLOCKS) {
    lines.push(`import { ${exportName} } from '${base}/${lang}/${file}.js';`);
  }
  lines.push('');
  for (const [key, base] of KB_SUBTITLE_MODULES) {
    lines.push(`import { kbSubtitle as kbSubtitle_${key} } from '${base}/${lang}/pages-kb-subtitle.js';`);
  }
  lines.push('');
  lines.push('export const pages = {');
  for (const [exportName] of PAGE_BLOCKS) {
    lines.push(`  ${exportName},`);
  }
  lines.push('  kbSubtitles: {');
  for (const [key] of KB_SUBTITLE_MODULES) {
    lines.push(`    ${key}: kbSubtitle_${key},`);
  }
  lines.push('  },');
  lines.push('} as const;');
  lines.push('');
  const out = path.join(srcRoot, 'i18n/locales', lang, 'pages.ts');
  fs.writeFileSync(out, lines.join('\n'));
  console.log(`wrote ${out}`);
}

writePages('en');
writePages('zh');
