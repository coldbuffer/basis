#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const srcRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../src');

const aliases = [
  ['t.kbReview', 't.review.queue'],
  ['t.kbGraphCanvas', 't.graph.canvas'],
  ['t.kbGraphPage', 't.graph.page'],
  ['t.kbGraphDiff', 't.graph.diff'],
  ['t.kbGraphProjection', 't.graph.projection'],
  ['t.kbGraphAudit', 't.graph.audit'],
  ['t.kbOntology', 't.ontology.hub'],
  ['t.kbShacl', 't.ontology.shacl'],
  ['t.kbAlignments', 't.ontology.alignments'],
  ['t.kbAnalyze', 't.analyze.hub'],
  ['t.kbReasoning', 't.analyze.reasoning'],
  ['t.kbSparql', 't.analyze.sparql'],
  ['t.kbSettings', 't.settings.panel'],
  ['t.kbOrgSso', 't.settings.org_sso'],
  ['t.kbOrgSaml', 't.settings.org_saml'],
  ['t.kbProcessing', 't.processing.jobs'],
  ['t.kbDecisions', 't.decisions.page'],
  ['t.kbConnectors', 't.connectors.page'],
  ['t.entityResolution', 't.entity_resolution.page'],
  ['t.kbMappings', 't.mappings.page'],
  ['t.kbSearch', 't.search.page'],
  ['t.kbSources', 't.library.sources'],
  ['t.kbVocabulary', 't.vocabulary.page'],
  ['t.kbLineage', 't.lineage.page'],
  ['t.kbLedger', 't.chrome.ledger'],
  ['t.kbWs', 't.chrome.ws'],
  ['t.kbImportExport', 't.chrome.import_export'],
  ['t.marketing', 't.home.marketing'],
  ['t.models', 't.admin_models.page'],
  ['t.platformSettings', 't.admin_settings.page'],
  ['messagesForLocale(loc).kbWs', 'messagesForLocale(loc).chrome.ws'],
  ['messagesForLocale(locale).kbWs', 'messagesForLocale(locale).chrome.ws'],
  ['messagesForLocale(kbWsHttpLocale(locale)).kbWs', 'messagesForLocale(kbWsHttpLocale(locale)).chrome.ws'],
  ["messagesForLocale(localeFromBrowser(lang)).kbWs", "messagesForLocale(localeFromBrowser(lang)).chrome.ws"],
  ['t.pages.alerts', 't.alerts.page'],
  ['t.pages.basisAudit', 't.admin_audit.page'],
  ['t.pages.basisKbs', 't.admin_workspaces.page'],
  ['t.pages.basisUsers', 't.admin_users.page'],
  ['t.pages.swagger', 't.swagger.page'],
  ['t.pages.kbSubtitles', 't._deprecated_kb_subtitles'],
  ["LocaleMessages['kbReview']", "LocaleMessages['review']['queue']"],
  ["LocaleMessages['kbSearch']", "LocaleMessages['search']['page']"],
  ["LocaleMessages['kbMappings']", "LocaleMessages['mappings']['page']"],
  ["LocaleMessages['kbSources']", "LocaleMessages['library']['sources']"],
  ["LocaleMessages['pages']['alerts']", "LocaleMessages['alerts']['page']"],
  ["LocaleMessages['pages']['basisAudit']", "LocaleMessages['admin_audit']['page']"],
  ["LocaleMessages['menu']['kbMcp']", "LocaleMessages['chrome']['menu']['kb_mcp']"],
  ["LocaleMessages['sidebar']", "LocaleMessages['chrome']['sidebar']"],
];

aliases.sort((a, b) => b[0].length - a[0].length);

function walk(dir, files = []) {
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name);
    if (name === 'node_modules') continue;
    if (fs.statSync(full).isDirectory()) walk(full, files);
    else if (/\.(tsx?)$/.test(name)) files.push(full);
  }
  return files;
}

let n = 0;
for (const file of walk(srcRoot)) {
  if (file.includes('/i18n/locales/') && !file.includes('pick-locale')) continue;
  let text = fs.readFileSync(file, 'utf8');
  let changed = false;
  for (const [from, to] of aliases) {
    if (!text.includes(from)) continue;
    text = text.split(from).join(to);
    changed = true;
  }
  if (changed) {
    fs.writeFileSync(file, text);
    n++;
  }
}
console.log(`Namespace alias pass: ${n} files`);
