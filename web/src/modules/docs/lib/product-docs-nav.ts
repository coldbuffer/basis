/** Public product documentation IA (marketing site `/docs/*`). */

export type DocSlug =
  | 'overview'
  | 'quickstart'
  | 'console-tour'
  | 'concepts'
  | 'architecture'
  | 'ontology-and-mappings'
  | 'governance-and-review'
  | 'connectors-overview'
  | 'rest-api'
  | 'auth'
  | 'mcp'
  | 'agent-workflows'
  | 'bocp-guide'
  | 'bocp'
  | 'connectors-basis'
  | 'guide-first-ingest'
  | 'guide-bocp-manifest'
  | 'guide-mcp-cursor'
  | 'guide-enterprise-sso'
  | 'guide-export-backup'
  | 'api-reference'
  | 'configuration'
  | 'limits-and-errors'
  | 'mcp-tools'
  | 'deployment'
  | 'production-checklist'
  | 'security';

/** All routable doc slugs (must match Fumadocs pages under `content/docs/{locale}/`). */
export const DOC_SLUGS: DocSlug[] = [
  'overview',
  'quickstart',
  'console-tour',
  'concepts',
  'architecture',
  'ontology-and-mappings',
  'governance-and-review',
  'connectors-overview',
  'rest-api',
  'auth',
  'mcp',
  'agent-workflows',
  'bocp-guide',
  'bocp',
  'connectors-basis',
  'guide-first-ingest',
  'guide-bocp-manifest',
  'guide-mcp-cursor',
  'guide-enterprise-sso',
  'guide-export-backup',
  'api-reference',
  'configuration',
  'limits-and-errors',
  'mcp-tools',
  'deployment',
  'production-checklist',
  'security',
];

export function docsPath(slug: DocSlug): string {
  return slug === 'overview' ? '/docs' : `/docs/${slug}`;
}

export function docSlugFromParam(param: string | undefined): DocSlug {
  if (!param || param === 'overview') return 'overview';
  if ((DOC_SLUGS as readonly string[]).includes(param)) return param as DocSlug;
  return 'overview';
}
