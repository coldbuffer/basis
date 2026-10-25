#!/usr/bin/env node
/**
 * Full i18n migration: module en/zh/index.ts, chrome/core index, new locales aggregator, path-map.json
 * Run from web/: npx tsx scripts/migrate-i18n-full.mjs && npx tsx scripts/codemod-i18n-paths.mjs
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const srcRoot = path.join(webRoot, 'src');
const localesEn = path.join(srcRoot, 'i18n/locales/en');
const mapOut = path.join(webRoot, 'scripts/i18n-path-map.json');

const { en: enOld } = await import(pathToFileURL(path.join(localesEn, 'index.ts')).href);
const { zh: zhOld } = await import(pathToFileURL(path.join(localesEn, '../zh/index.ts')).href);

function camelToSnake(key) {
  return key
    .replace(/([A-Z])/g, '_$1')
    .toLowerCase()
    .replace(/^_/, '')
    .replace(/-/g, '_');
}

function deepSnakeKeys(obj) {
  if (typeof obj === 'string') return obj;
  if (!obj || typeof obj !== 'object') return obj;
  const out = {};
  for (const [k, v] of Object.entries(obj)) {
    out[camelToSnake(k)] = deepSnakeKeys(v);
  }
  return out;
}

function flattenStrings(obj, prefix = '') {
  const paths = {};
  if (typeof obj === 'string') {
    paths[prefix] = obj;
    return paths;
  }
  if (!obj || typeof obj !== 'object') return paths;
  for (const [k, v] of Object.entries(obj)) {
    const p = prefix ? `${prefix}.${k}` : k;
    Object.assign(paths, flattenStrings(v, p));
  }
  return paths;
}

/** old top-level export name -> [namespace, area] */
const KB_NS_AREA = {
  kbReview: ['review', 'queue'],
  kbGraphCanvas: ['graph', 'canvas'],
  kbGraphPage: ['graph', 'page'],
  kbGraphDiff: ['graph', 'diff'],
  kbGraphProjection: ['graph', 'projection'],
  kbGraphAudit: ['graph', 'audit'],
  kbOntology: ['ontology', 'hub'],
  kbShacl: ['ontology', 'shacl'],
  kbAlignments: ['ontology', 'alignments'],
  kbAnalyze: ['analyze', 'hub'],
  kbReasoning: ['analyze', 'reasoning'],
  kbSparql: ['analyze', 'sparql'],
  kbSettings: ['settings', 'panel'],
  kbOrgSso: ['settings', 'org_sso'],
  kbOrgSaml: ['settings', 'org_saml'],
  kbProcessing: ['processing', 'jobs'],
  kbDecisions: ['decisions', 'page'],
  kbConnectors: ['connectors', 'page'],
  entityResolution: ['entity_resolution', 'page'],
  kbMappings: ['mappings', 'page'],
  kbSearch: ['search', 'page'],
  kbSources: ['library', 'sources'],
  kbVocabulary: ['vocabulary', 'page'],
  kbLineage: ['lineage', 'page'],
  models: ['admin_models', 'page'],
  platformSettings: ['admin_settings', 'page'],
  platformAuditActions: ['admin_audit', 'actions'],
  login: ['login', 'page'],
  marketing: ['home', 'marketing'],
  docs: ['docs', 'page'],
  kbLedger: ['chrome', 'ledger'],
  kbWs: ['chrome', 'ws'],
  kbImportExport: ['chrome', 'import_export'],
};

const KB_SUBTITLE_NS = {
  review: 'review',
  search: 'search',
  analyze: 'analyze',
  entities: 'entities',
  sources: 'library',
  connectors: 'connectors',
  processing: 'processing',
  graphDiff: 'graph',
  alerts: 'alerts',
  settings: 'settings',
};

const MENU_KB_NS = {
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

const PAGE_BLOCK_NS = {
  alerts: 'alerts',
  basisKbs: 'admin_workspaces',
  basisAudit: 'admin_audit',
  basisUsers: 'admin_users',
  swagger: 'swagger',
};

const pathMap = {};

function addMap(oldPath, newPath) {
  pathMap[oldPath] = newPath;
}

function setNested(target, parts, value) {
  let cur = target;
  for (let i = 0; i < parts.length - 1; i++) {
    const p = parts[i];
    if (!cur[p]) cur[p] = {};
    cur = cur[p];
  }
  cur[parts[parts.length - 1]] = value;
}

function buildLocaleTrees(oldLocale) {
  const namespaces = {};

  for (const [oldNs, [ns, area]] of Object.entries(KB_NS_AREA)) {
    const block = oldLocale[oldNs];
    if (!block) continue;
    if (!namespaces[ns]) namespaces[ns] = {};
    namespaces[ns][area] = deepSnakeKeys(block);
    const flat = flattenStrings(block);
    for (const [leaf, _] of Object.entries(flat)) {
      const snakeLeaf = leaf
        .split('.')
        .map((p) => camelToSnake(p))
        .join('.');
      addMap(`${oldNs}.${leaf}`, `${ns}.${area}.${snakeLeaf}`);
    }
  }

  for (const [key, ns] of Object.entries(PAGE_BLOCK_NS)) {
    const block = oldLocale.pages?.[key];
    if (!block) continue;
    if (!namespaces[ns]) namespaces[ns] = {};
    namespaces[ns].page = { ...namespaces[ns].page, ...deepSnakeKeys(block) };
    const flat = flattenStrings(block);
    for (const [leaf] of Object.entries(flat)) {
      const snakeLeaf = leaf.split('.').map(camelToSnake).join('.');
      addMap(`pages.${key}.${leaf}`, `${ns}.page.${snakeLeaf}`);
    }
  }

  for (const [key, ns] of Object.entries(KB_SUBTITLE_NS)) {
    const sub = oldLocale.pages?.kbSubtitles?.[key];
    if (sub === undefined) continue;
    if (!namespaces[ns]) namespaces[ns] = {};
    if (!namespaces[ns].page) namespaces[ns].page = {};
    namespaces[ns].page.subtitle = sub;
    addMap(`pages.kbSubtitles.${key}`, `${ns}.page.subtitle`);
  }

  for (const [key, label] of Object.entries(oldLocale.menu?.kb ?? {})) {
    const ns = MENU_KB_NS[key];
    if (!ns) continue;
    if (!namespaces[ns]) namespaces[ns] = {};
    if (!namespaces[ns].menu) namespaces[ns].menu = {};
    const snakeKey = camelToSnake(key);
    namespaces[ns].menu[snakeKey] = label;
    addMap(`menu.kb.${key}`, `${ns}.menu.${snakeKey}`);
  }

  const chrome = {
    menu: {
      platform: deepSnakeKeys(oldLocale.menu.platform),
      kb_zones: deepSnakeKeys(oldLocale.menu.kbZones),
      groups: deepSnakeKeys(oldLocale.menu.groups),
      kb_switcher: deepSnakeKeys(oldLocale.menu.kbSwitcher),
      placeholder: deepSnakeKeys(oldLocale.menu.placeholder),
      capabilities: deepSnakeKeys(oldLocale.menu.capabilities),
      kb_settings: deepSnakeKeys(oldLocale.menu.kbSettings),
      kb_integration: deepSnakeKeys(oldLocale.menu.kbIntegration),
      kb_mcp: deepSnakeKeys(oldLocale.menu.kbMcp),
      models: deepSnakeKeys(oldLocale.menu.models),
      system: deepSnakeKeys(oldLocale.menu.system),
    },
    sidebar: deepSnakeKeys(oldLocale.sidebar),
    nav: deepSnakeKeys(oldLocale.nav),
    ws: namespaces.chrome?.ws ?? deepSnakeKeys(oldLocale.kbWs),
    ledger: namespaces.chrome?.ledger ?? deepSnakeKeys(oldLocale.kbLedger),
    import_export: namespaces.chrome?.import_export ?? deepSnakeKeys(oldLocale.kbImportExport),
  };
  delete namespaces.chrome;

  const flatMenu = flattenStrings(oldLocale.menu);
  for (const [leaf] of Object.entries(flatMenu)) {
    if (leaf.startsWith('kb.')) continue;
    const parts = leaf.split('.').map(camelToSnake);
    if (parts[0] === 'kbZones') {
      addMap(
        `menu.${leaf}`,
        `core.workspace_nav.workspace_zones.${parts.slice(1).map(camelToSnake).join('.')}`,
      );
      continue;
    }
    if (parts[0] === 'kbSwitcher') {
      const switchLeaf = parts.slice(1).map(camelToSnake).join('.');
      const mapped = switchLeaf === 'all_kbs' ? 'all_workspaces' : switchLeaf;
      addMap(`menu.${leaf}`, `core.workspace_nav.workspace_switcher.${mapped}`);
      continue;
    }
    if (parts[0] === 'kbSettings') {
      const tabLeaf = parts.slice(1).map(camelToSnake).join('.');
      const tabKey = tabLeaf === 'delete_kb' ? 'delete_workspace' : tabLeaf;
      addMap(`menu.${leaf}`, `settings.tabs.${tabKey}`);
      continue;
    }
    if (parts[0] === 'kbIntegration') {
      const rest = parts.slice(1).map(camelToSnake).join('.');
      addMap(`menu.${leaf}`, `integration.${rest.replace('openapi.kb_id_try_it_out', 'openapi.workspace_id_try_it_out')}`);
      continue;
    }
    if (parts[0] === 'kbMcp') {
      addMap(`menu.${leaf}`, `integration.mcp.${parts.slice(1).map(camelToSnake).join('.')}`);
      continue;
    }
    if (parts[0] === 'platform') {
      const platLeaf = parts[1] === 'kbs' ? 'workspaces' : camelToSnake(parts[1]);
      const rest = parts.slice(2).map(camelToSnake).join('.');
      const target = rest
        ? `core.workspace_nav.platform.${platLeaf}.${rest}`
        : `core.workspace_nav.platform.${platLeaf}`;
      addMap(`menu.${leaf}`, target);
      continue;
    }
    if (parts[0] === 'groups' || parts[0] === 'placeholder' || parts[0] === 'capabilities') {
      addMap(`menu.${leaf}`, `core.workspace_nav.${parts.map(camelToSnake).join('.')}`);
      continue;
    }
    addMap(`menu.${leaf}`, `chrome.menu.${parts.map(camelToSnake).join('.')}`);
  }

  const flatSidebar = flattenStrings(oldLocale.sidebar);
  for (const [leaf] of Object.entries(flatSidebar)) {
    const snake = camelToSnake(leaf);
    const mapped = snake === 'back_to_knowledge_console' ? 'back_to_workspace_console' : snake;
    addMap(`sidebar.${leaf}`, `core.shell.sidebar.${mapped}`);
  }
  const flatNav = flattenStrings(oldLocale.nav);
  for (const [leaf] of Object.entries(flatNav)) {
    const snake = camelToSnake(leaf);
    const mapped = snake === 'kb_alerts' ? 'workspace_alerts' : snake;
    const ns = snake === 'kb_alerts' ? 'alerts.menu' : 'chrome.nav';
    addMap(`nav.${leaf}`, `${ns}.${mapped}`);
  }

  return { namespaces, chrome };
}

function serialize(obj, indent = 0) {
  const sp = '  '.repeat(indent);
  if (typeof obj === 'string') return JSON.stringify(obj);
  const lines = Object.entries(obj).map(([k, v]) => {
    const key = /^[a-zA-Z_][\w]*$/.test(k) ? k : JSON.stringify(k);
    return `${sp}  ${key}: ${serialize(v, indent + 1)},`;
  });
  return `{\n${lines.join('\n')}\n${sp}}`;
}

function writeModuleIndex(ns, tree, lang) {
  const seg = ns.replace(/_/g, '-');
  const candidates = [
    path.join(srcRoot, 'modules', seg, 'i18n', lang),
    path.join(srcRoot, 'modules', ns, 'i18n', lang),
  ];
  let dir = candidates.find((d) => fs.existsSync(path.join(srcRoot, 'modules', seg)));
  if (!dir) {
    dir = path.join(srcRoot, 'modules', seg, 'i18n', lang);
  }
  dir = path.join(srcRoot, 'modules', seg, 'i18n', lang);
  if (!fs.existsSync(path.join(srcRoot, 'modules', seg))) {
    console.warn(`skip namespace ${ns}, no module folder ${seg}`);
    return;
  }
  fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, 'index.ts');
  fs.writeFileSync(file, `export const ${ns} = ${serialize(tree)} as const;\n`);
  if (lang === 'en') {
    const rootIndex = path.join(srcRoot, 'modules', seg, 'i18n', 'index.ts');
    fs.writeFileSync(
      rootIndex,
      `/** Edit \`en/index.ts\` and \`zh/index.ts\`; namespace \`${ns}\`. */\nexport { ${ns} } from './en/index.js';\n`,
    );
  }
}

function cleanLegacyI18nFiles(modDir) {
  const i18nRoot = path.join(modDir, 'i18n');
  for (const lang of ['en', 'zh']) {
    const langDir = path.join(i18nRoot, lang);
    if (!fs.existsSync(langDir)) continue;
    for (const f of fs.readdirSync(langDir)) {
      if (f !== 'index.ts') fs.unlinkSync(path.join(langDir, f));
    }
  }
}

const enBuilt = buildLocaleTrees(enOld);
const zhBuilt = buildLocaleTrees(zhOld);

for (const ns of new Set([...Object.keys(enBuilt.namespaces), ...Object.keys(zhBuilt.namespaces)])) {
  writeModuleIndex(ns, enBuilt.namespaces[ns] ?? {}, 'en');
  writeModuleIndex(ns, zhBuilt.namespaces[ns] ?? {}, 'zh');
  const seg = ns.replace(/_/g, '-');
  const modDir = path.join(srcRoot, 'modules', seg);
  if (fs.existsSync(modDir)) cleanLegacyI18nFiles(modDir);
}

for (const lang of ['en', 'zh']) {
  const chrome = lang === 'en' ? enBuilt.chrome : zhBuilt.chrome;
  const dir = path.join(srcRoot, 'chrome', 'i18n', lang);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'index.ts'), `export const chrome = ${serialize(chrome)} as const;\n`);
  for (const f of fs.readdirSync(dir)) {
    if (f !== 'index.ts') fs.unlinkSync(path.join(dir, f));
  }
}

const coreNs = {
  common: enOld.common,
  api_error_codes: deepSnakeKeys(enOld.apiErrorCodes),
  dev: enOld.dev,
};
const coreNsZh = {
  common: zhOld.common,
  api_error_codes: deepSnakeKeys(zhOld.apiErrorCodes),
  dev: zhOld.dev,
};

for (const [lang, core] of [['en', coreNs], ['zh', coreNsZh]]) {
  const dir = path.join(srcRoot, 'i18n/core', lang);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(
    path.join(dir, 'index.ts'),
    `export const core = ${serialize(core)} as const;\n`,
  );
  for (const f of ['common.ts', 'apiErrorCodes.ts', 'dev.ts']) {
    const p = path.join(dir, f);
    if (fs.existsSync(p)) fs.unlinkSync(p);
  }
}

const flatApi = flattenStrings(enOld.apiErrorCodes);
for (const [leaf] of Object.entries(flatApi)) {
  addMap(`apiErrorCodes.${leaf}`, `core.api_error_codes.${camelToSnake(leaf)}`);
}

function writeAggregator(lang, built, coreImport) {
  const imports = [];
  const entries = [];
  imports.push(`import { core } from '@/i18n/core/${lang}/index.js';`);
  imports.push(`import { chrome } from '@/chrome/i18n/${lang}/index.js';`);
  entries.push('core', 'chrome');

  for (const ns of Object.keys(built.namespaces).sort()) {
    const seg = ns.replace(/_/g, '-');
    imports.push(`import { ${ns} } from '@/modules/${seg}/i18n/${lang}/index.js';`);
    entries.push(ns);
  }

  const lines = [
    '/** Aggregated locale (module namespaces + chrome + core). */',
    '',
    ...imports,
    '',
    `export const ${lang} = {`,
    ...entries.map((e) => `  ${e},`),
    '} as const;',
    '',
  ];
  if (lang === 'en') lines.push('export type LocaleMessages = typeof en;', '');
  fs.writeFileSync(path.join(srcRoot, 'i18n/locales', lang, 'index.ts'), lines.join('\n'));
}

writeAggregator('en', enBuilt);
writeAggregator('zh', { namespaces: zhBuilt.namespaces });

for (const lang of ['en', 'zh']) {
  for (const f of ['menu.ts', 'pages.ts', 'menu-kb-keys.ts', 'nav.ts', 'sidebar.ts', 'apiErrorCodes.ts', 'dev.ts']) {
    const p = path.join(srcRoot, 'i18n/locales', lang, f);
    if (fs.existsSync(p)) fs.unlinkSync(p);
  }
}

fs.writeFileSync(mapOut, JSON.stringify(pathMap, null, 2));
console.log(`Wrote ${Object.keys(pathMap).length} path mappings to i18n-path-map.json`);
