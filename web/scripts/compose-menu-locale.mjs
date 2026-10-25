#!/usr/bin/env node
// Regenerate i18n/locales/{en,zh}/menu.ts from chrome + module fragments.
// Run: npx tsx scripts/compose-menu-locale.mjs
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const srcRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../src');

const KB_MODULE_IMPORTS = [
  ['graph', '@/modules/graph/i18n'],
  ['connectors', '@/modules/connectors/i18n'],
  ['search', '@/modules/search/i18n'],
  ['library', '@/modules/library/i18n'],
  ['processing', '@/modules/processing/i18n'],
  ['entities', '@/modules/entities/i18n'],
  ['review', '@/modules/review/i18n'],
  ['ontology', '@/modules/ontology/i18n'],
  ['analyze', '@/modules/analyze/i18n'],
  ['mappings', '@/modules/mappings/i18n'],
  ['vocabulary', '@/modules/vocabulary/i18n'],
  ['lineage', '@/modules/lineage/i18n'],
  ['alerts', '@/modules/alerts/i18n'],
  ['integration', '@/modules/integration/i18n'],
  ['settings', '@/modules/settings/i18n'],
];

const MENU_BLOCKS = [
  ['kbSettings', '@/modules/settings/i18n', 'menu-kbSettings'],
  ['kbIntegration', '@/modules/integration/i18n', 'menu-kbIntegration'],
  ['kbMcp', '@/modules/integration/i18n', 'menu-kbMcp'],
  ['models', '@/modules/admin-models/i18n', 'menu-models'],
  ['system', '@/modules/admin-settings/i18n', 'menu-system'],
];

const CHROME_MENU = [
  'platform',
  'groups',
  'kbZones',
  'kbSwitcher',
  'placeholder',
  'capabilities',
];

const KB_KEY_ORDER = [
  'graph',
  'search',
  'sources',
  'connectors',
  'connectorCatalog',
  'connectorStreamMappings',
  'connectorActionPolicy',
  'connectorRunLogs',
  'processing',
  'entities',
  'review',
  'ontology',
  'analyze',
  'mappings',
  'vocabulary',
  'lineage',
  'graphDiff',
  'alerts',
  'integration',
  'settings',
];

function writeMenu(lang) {
  const lines = [];
  lines.push('/** Composed from module and chrome menu fragments. */');
  lines.push('');
  const chromeFile = {
    platform: 'menu-platform',
    groups: 'menu-groups',
    kbZones: 'menu-kb-zones',
    kbSwitcher: 'menu-kb-switcher',
    placeholder: 'menu-placeholder',
    capabilities: 'menu-capabilities',
  };
  for (const name of CHROME_MENU) {
    lines.push(`import { ${name} } from '@/chrome/i18n/${lang}/${chromeFile[name]}.js';`);
  }
  for (const [exportName, base, file] of MENU_BLOCKS) {
    lines.push(`import { ${exportName} } from '${base}/${lang}/${file}.js';`);
  }
  lines.push('');
  lines.push('import type { MenuKbKey } from "./menu-kb-keys.js";');
  lines.push('');

  for (const [alias, base] of KB_MODULE_IMPORTS) {
    lines.push(`import { menuKb as menuKb_${alias} } from '${base}/${lang}/menu-kb.js';`);
  }
  lines.push('');
  lines.push('export const menu = {');
  lines.push('  platform,');
  lines.push('  kb: {');
  const keyToAlias = {
    graph: 'graph',
    graphDiff: 'graph',
    search: 'search',
    sources: 'library',
    connectors: 'connectors',
    connectorCatalog: 'connectors',
    connectorStreamMappings: 'connectors',
    connectorActionPolicy: 'connectors',
    connectorRunLogs: 'connectors',
    processing: 'processing',
    entities: 'entities',
    review: 'review',
    ontology: 'ontology',
    analyze: 'analyze',
    mappings: 'mappings',
    vocabulary: 'vocabulary',
    lineage: 'lineage',
    alerts: 'alerts',
    integration: 'integration',
    settings: 'settings',
  };
  for (const key of KB_KEY_ORDER) {
    const alias = keyToAlias[key];
    lines.push(`    ${key}: menuKb_${alias}.${key},`);
  }
  lines.push('  } satisfies Record<MenuKbKey, string>,');
  for (const name of CHROME_MENU) {
    if (name === 'platform') continue;
    lines.push(`  ${name},`);
  }
  for (const [exportName] of MENU_BLOCKS) {
    lines.push(`  ${exportName},`);
  }
  lines.push('} as const;');
  lines.push('');
  const out = path.join(srcRoot, 'i18n/locales', lang, 'menu.ts');
  fs.writeFileSync(out, lines.join('\n'));
  console.log(`wrote ${out}`);
}

writeMenu('en');
writeMenu('zh');
