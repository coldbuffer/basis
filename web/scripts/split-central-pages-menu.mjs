#!/usr/bin/env node
/**
 * Split i18n/locales/{en,zh}/pages.ts and menu.ts into module/chrome fragments; rewrite central files as aggregators.
 * Run from web/: npx tsx scripts/split-central-pages-menu.mjs
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const srcRoot = path.join(webRoot, 'src');
const localesEn = path.join(srcRoot, 'i18n/locales/en');
const localesZh = path.join(srcRoot, 'i18n/locales/zh');

const { pages: pagesEn } = await import(pathToFileURL(path.join(localesEn, 'pages.ts')).href);
const { pages: pagesZh } = await import(pathToFileURL(path.join(localesZh, 'pages.ts')).href);
const { menu: menuEn } = await import(pathToFileURL(path.join(localesEn, 'menu.ts')).href);
const { menu: menuZh } = await import(pathToFileURL(path.join(localesZh, 'menu.ts')).href);

const PAGE_BLOCK_TARGETS = {
  alerts: 'modules/alerts',
  basisKbs: 'modules/admin-workspaces',
  basisAudit: 'modules/admin-audit',
  basisUsers: 'modules/admin-users',
  swagger: 'modules/swagger',
};

const KB_SUBTITLE_TARGETS = {
  review: 'modules/review',
  search: 'modules/search',
  analyze: 'modules/analyze',
  entities: 'modules/entities',
  sources: 'modules/library',
  connectors: 'modules/connectors',
  processing: 'modules/processing',
  graphDiff: 'modules/graph',
  alerts: 'modules/alerts',
  settings: 'modules/settings',
};

const MENU_BLOCK_TARGETS = {
  kbSettings: 'modules/settings',
  kbIntegration: 'modules/integration',
  kbMcp: 'modules/integration',
  models: 'modules/admin-models',
  system: 'modules/admin-settings',
};

const MENU_KB_LABEL_TARGETS = {
  graph: 'modules/graph',
  search: 'modules/search',
  sources: 'modules/library',
  connectors: 'modules/connectors',
  connectorCatalog: 'modules/connectors',
  connectorStreamMappings: 'modules/connectors',
  connectorActionPolicy: 'modules/connectors',
  connectorRunLogs: 'modules/connectors',
  processing: 'modules/processing',
  entities: 'modules/entities',
  review: 'modules/review',
  ontology: 'modules/ontology',
  analyze: 'modules/analyze',
  mappings: 'modules/mappings',
  vocabulary: 'modules/vocabulary',
  lineage: 'modules/lineage',
  graphDiff: 'modules/graph',
  alerts: 'modules/alerts',
  integration: 'modules/integration',
  settings: 'modules/settings',
};

function ensureDir(d) {
  fs.mkdirSync(d, { recursive: true });
}

function destDir(targetRel, lang) {
  if (targetRel === 'chrome') return path.join(srcRoot, 'chrome', 'i18n', lang);
  return path.join(srcRoot, targetRel, 'i18n', lang);
}

function serializeValue(value, indent = 2) {
  if (typeof value === 'string') {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    const inner = value.map((v) => `${' '.repeat(indent + 2)}${serializeValue(v, indent + 2)}`).join(',\n');
    return `[\n${inner}\n${' '.repeat(indent)}]`;
  }
  if (value && typeof value === 'object') {
    const entries = Object.entries(value);
    const inner = entries
      .map(([k, v]) => {
        const key = /^[a-zA-Z_][\w$]*$/.test(k) && !k.includes('.') ? k : JSON.stringify(k);
        return `${' '.repeat(indent + 2)}${key}: ${serializeValue(v, indent + 2)},`;
      })
      .join('\n');
    return `{\n${inner}\n${' '.repeat(indent)}}`;
  }
  return String(value);
}

function writeExport(filePath, exportName, value) {
  const body = `export const ${exportName} = ${serializeValue(value)} as const;\n`;
  fs.writeFileSync(filePath, body);
}

function relImport(fromDir, absTarget) {
  let rel = path.relative(fromDir, absTarget).replace(/\\/g, '/');
  if (!rel.startsWith('.')) rel = `./${rel}`;
  return rel.replace(/\.ts$/, '.js');
}

for (const lang of ['en', 'zh']) {
  const pages = lang === 'en' ? pagesEn : pagesZh;

  for (const [block, targetRel] of Object.entries(PAGE_BLOCK_TARGETS)) {
    const dir = destDir(targetRel, lang);
    ensureDir(dir);
    writeExport(path.join(dir, `pages-${block}.ts`), block, pages[block]);
  }

  for (const [key, targetRel] of Object.entries(KB_SUBTITLE_TARGETS)) {
    const dir = destDir(targetRel, lang);
    ensureDir(dir);
    writeExport(path.join(dir, 'pages-kb-subtitle.ts'), 'kbSubtitle', pages.kbSubtitles[key]);
  }
}

for (const lang of ['en', 'zh']) {
  const menu = lang === 'en' ? menuEn : menuZh;

  for (const [block, targetRel] of Object.entries(MENU_BLOCK_TARGETS)) {
    const dir = destDir(targetRel, lang);
    ensureDir(dir);
    writeExport(path.join(dir, `menu-${block}.ts`), block, menu[block]);
  }

  for (const [key, targetRel] of Object.entries(MENU_KB_LABEL_TARGETS)) {
    const dir = destDir(targetRel, lang);
    ensureDir(dir);
    writeExport(path.join(dir, 'menu-kb-label.ts'), 'menuKbLabel', menu.kb[key]);
  }

  const chromeMenuDir = destDir('chrome', lang);
  ensureDir(chromeMenuDir);
  writeExport(path.join(chromeMenuDir, 'menu-kb-zones.ts'), 'kbZones', menu.kbZones);
  writeExport(path.join(chromeMenuDir, 'menu-kb-switcher.ts'), 'kbSwitcher', menu.kbSwitcher);
  writeExport(path.join(chromeMenuDir, 'menu-placeholder.ts'), 'placeholder', menu.placeholder);
  writeExport(path.join(chromeMenuDir, 'menu-capabilities.ts'), 'capabilities', menu.capabilities);
  writeExport(path.join(chromeMenuDir, 'menu-platform.ts'), 'platform', menu.platform);
  writeExport(path.join(chromeMenuDir, 'menu-groups.ts'), 'groups', menu.groups);
}

function writePagesAggregator(lang) {
  const fromDir = path.join(srcRoot, 'i18n/locales', lang);
  const lines = [];
  lines.push('/** Composed from module page fragments. */');
  lines.push('');
  for (const block of Object.keys(PAGE_BLOCK_TARGETS)) {
    const target = PAGE_BLOCK_TARGETS[block];
    const imp = relImport(fromDir, path.join(destDir(target, lang), `pages-${block}.ts`));
    lines.push(`import { ${block} } from '${imp}';`);
  }
  lines.push('');
  for (const key of Object.keys(KB_SUBTITLE_TARGETS)) {
    const target = KB_SUBTITLE_TARGETS[key];
    const imp = relImport(fromDir, path.join(destDir(target, lang), 'pages-kb-subtitle.ts'));
    lines.push(`import { kbSubtitle as kbSubtitle_${key} } from '${imp}';`);
  }
  lines.push('');
  lines.push('export const pages = {');
  for (const block of Object.keys(PAGE_BLOCK_TARGETS)) {
    lines.push(`  ${block},`);
  }
  lines.push('  kbSubtitles: {');
  for (const key of Object.keys(KB_SUBTITLE_TARGETS)) {
    lines.push(`    ${key}: kbSubtitle_${key},`);
  }
  lines.push('  },');
  lines.push('} as const;');
  lines.push('');
  fs.writeFileSync(path.join(fromDir, 'pages.ts'), lines.join('\n'));
}

function writeMenuAggregator(lang) {
  const fromDir = path.join(srcRoot, 'i18n/locales', lang);
  const lines = [];
  lines.push('/** Composed from module and chrome menu fragments. */');
  lines.push('');
  const chromeDir = destDir('chrome', lang);
  for (const [exportName, file] of [
    ['platform', 'menu-platform'],
    ['groups', 'menu-groups'],
    ['kbZones', 'menu-kb-zones'],
    ['kbSwitcher', 'menu-kb-switcher'],
    ['placeholder', 'menu-placeholder'],
    ['capabilities', 'menu-capabilities'],
  ]) {
    const imp = relImport(fromDir, path.join(chromeDir, `${file}.ts`));
    lines.push(`import { ${exportName} } from '${imp}';`);
  }
  for (const [block, target] of Object.entries(MENU_BLOCK_TARGETS)) {
    const imp = relImport(fromDir, path.join(destDir(target, lang), `menu-${block}.ts`));
    lines.push(`import { ${block} } from '${imp}';`);
  }
  lines.push('');
  lines.push('import type { MenuKbKey } from "./menu-kb-keys.js";');
  lines.push('');
  for (const key of Object.keys(MENU_KB_LABEL_TARGETS)) {
    const target = MENU_KB_LABEL_TARGETS[key];
    const imp = relImport(fromDir, path.join(destDir(target, lang), 'menu-kb-label.ts'));
    lines.push(`import { menuKbLabel as menuKb_${key} } from '${imp}';`);
  }
  lines.push('');
  lines.push('export const menu = {');
  lines.push('  platform,');
  lines.push('  kb: {');
  for (const key of Object.keys(MENU_KB_LABEL_TARGETS)) {
    lines.push(`    ${key}: menuKb_${key},`);
  }
  lines.push('  } satisfies Record<MenuKbKey, string>,');
  lines.push('  kbZones,');
  lines.push('  groups,');
  lines.push('  kbSwitcher,');
  lines.push('  placeholder,');
  lines.push('  capabilities,');
  for (const block of Object.keys(MENU_BLOCK_TARGETS)) {
    lines.push(`  ${block},`);
  }
  lines.push('} as const;');
  lines.push('');
  fs.writeFileSync(path.join(fromDir, 'menu.ts'), lines.join('\n'));
}

// menu.kb keys for satisfies
const menuKbKeys = Object.keys(MENU_KB_LABEL_TARGETS);
fs.writeFileSync(
  path.join(localesEn, 'menu-kb-keys.ts'),
  `export type MenuKbKey =\n  | ${menuKbKeys.map((k) => JSON.stringify(k)).join('\n  | ')};\n`,
);
fs.writeFileSync(
  path.join(localesZh, 'menu-kb-keys.ts'),
  fs.readFileSync(path.join(localesEn, 'menu-kb-keys.ts')),
);

writePagesAggregator('en');
writePagesAggregator('zh');
writeMenuAggregator('en');
writeMenuAggregator('zh');

console.log('Split pages.ts and menu.ts into module/chrome fragments.');
