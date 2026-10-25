#!/usr/bin/env node
/**
 * Move locale namespace files from i18n/locales/{en,zh}/ into module (or chrome) i18n folders.
 * Regenerates i18n/locales/{en,zh}/index.ts as aggregator. Run once from web/: node scripts/migrate-locales-to-modules.mjs
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const srcRoot = path.join(webRoot, 'src');
const localesRoot = path.join(srcRoot, 'i18n/locales');

/** basename without .ts -> relative dir under src/ (modules/… or chrome/i18n) */
const FILE_TARGETS = {
  entityResolution: 'modules/entity-resolution',
  kbMappings: 'modules/mappings',
  kbSearch: 'modules/search',
  kbSources: 'modules/library',
  kbVocabulary: 'modules/vocabulary',
  kbReasoning: 'modules/analyze',
  kbSparql: 'modules/analyze',
  kbAnalyze: 'modules/analyze',
  kbGraphCanvas: 'modules/graph',
  graphEffectReasons: 'modules/graph',
  graphPlugins: 'modules/graph',
  kbGraphPage: 'modules/graph',
  kbGraphDiff: 'modules/graph',
  kbGraphProjection: 'modules/graph',
  kbGraphAudit: 'modules/graph',
  kbReview: 'modules/review',
  kbShacl: 'modules/ontology',
  kbAlignments: 'modules/ontology',
  kbOntology: 'modules/ontology',
  kbLineage: 'modules/lineage',
  kbSettings: 'modules/settings',
  kbOrgSso: 'modules/settings',
  kbOrgSaml: 'modules/settings',
  kbProcessing: 'modules/processing',
  kbDecisions: 'modules/decisions',
  kbConnectors: 'modules/connectors',
  models: 'modules/admin-models',
  platformSettings: 'modules/admin-settings',
  platformAuditActions: 'modules/admin-audit',
  login: 'modules/login',
  docs: 'modules/docs',
  marketing: 'modules/home',
  kbLedger: 'chrome',
  kbWs: 'chrome',
  kbImportExport: 'chrome',
};

const CENTRAL_EN = [
  'menu',
  'common',
  'nav',
  'pages',
  'sidebar',
  'apiErrorCodes',
  'dev',
];

const AGGREGATED = [
  ['models', 'modules/admin-models'],
  ['login', 'modules/login'],
  ['marketing', 'modules/home'],
  ['docs', 'modules/docs'],
  ['entityResolution', 'modules/entity-resolution'],
  ['kbMappings', 'modules/mappings'],
  ['kbSearch', 'modules/search'],
  ['kbSources', 'modules/library'],
  ['kbLedger', 'chrome'],
  ['kbGraphDiff', 'modules/graph'],
  ['kbVocabulary', 'modules/vocabulary'],
  ['kbReasoning', 'modules/analyze'],
  ['kbGraphCanvas', 'modules/graph'],
  ['kbGraphAudit', 'modules/graph'],
  ['platformAuditActions', 'modules/admin-audit'],
  ['kbReview', 'modules/review'],
  ['kbShacl', 'modules/ontology'],
  ['kbWs', 'chrome'],
  ['kbAlignments', 'modules/ontology'],
  ['kbImportExport', 'chrome'],
  ['kbGraphPage', 'modules/graph'],
  ['kbGraphProjection', 'modules/graph'],
  ['kbSparql', 'modules/analyze'],
  ['kbLineage', 'modules/lineage'],
  ['kbSettings', 'modules/settings'],
  ['kbOrgSso', 'modules/settings'],
  ['kbOrgSaml', 'modules/settings'],
  ['platformSettings', 'modules/admin-settings'],
  ['kbOntology', 'modules/ontology'],
  ['kbAnalyze', 'modules/analyze'],
  ['kbProcessing', 'modules/processing'],
  ['kbDecisions', 'modules/decisions'],
  ['kbConnectors', 'modules/connectors'],
];

function ensureDir(d) {
  fs.mkdirSync(d, { recursive: true });
}

function localeDestDir(targetRel, lang) {
  if (targetRel === 'chrome') {
    return path.join(srcRoot, 'chrome', 'i18n', lang);
  }
  return path.join(srcRoot, targetRel, 'i18n', lang);
}

function moveLocaleFile(lang, baseName) {
  const targetRel = FILE_TARGETS[baseName];
  if (!targetRel) return;
  const from = path.join(localesRoot, lang, `${baseName}.ts`);
  if (!fs.existsSync(from)) {
    console.warn(`skip missing ${from}`);
    return;
  }
  const toDir = localeDestDir(targetRel, lang);
  ensureDir(toDir);
  const to = path.join(toDir, `${baseName}.ts`);
  fs.renameSync(from, to);
  const label =
    targetRel === 'chrome'
      ? `chrome/i18n/${lang}/`
      : `${targetRel}/i18n/${lang}/`;
  console.log(`moved ${lang}/${baseName}.ts -> ${label}`);
}

for (const base of Object.keys(FILE_TARGETS)) {
  moveLocaleFile('en', base);
  moveLocaleFile('zh', base);
}

function importPath(targetRel, baseName, lang) {
  const abs = path.join(localeDestDir(targetRel, lang), `${baseName}.ts`);
  let rel = path.relative(path.join(localesRoot, lang), abs).replace(/\\/g, '/');
  if (!rel.startsWith('.')) rel = `./${rel}`;
  return rel.replace(/\.ts$/, '.js');
}

function writeIndex(lang, exportName) {
  const lines = [];
  lines.push('/** Aggregated locale; feature namespaces live under modules and chrome i18n trees. */');
  lines.push('');
  for (const base of CENTRAL_EN) {
    lines.push(`import { ${base} } from './${base}.js';`);
  }
  for (const [base, targetRel] of AGGREGATED) {
    const imp = importPath(targetRel, base, lang);
    lines.push(`import { ${base} } from '${imp}';`);
  }
  lines.push('');
  lines.push(`export const ${exportName} = {`);
  for (const base of CENTRAL_EN) {
    lines.push(`  ${base},`);
  }
  for (const [base] of AGGREGATED) {
    lines.push(`  ${base},`);
  }
  lines.push('} as const;');
  lines.push('');
  if (lang === 'en') {
    lines.push(`export type LocaleMessages = typeof ${exportName};`);
    lines.push('');
  }
  const indexPath = path.join(localesRoot, lang, 'index.ts');
  fs.writeFileSync(indexPath, lines.join('\n'));
  console.log(`wrote ${indexPath}`);
}

writeIndex('en', 'en');
writeIndex('zh', 'zh');

console.log('Done. Run npm run typecheck && npm run audit:locale');
