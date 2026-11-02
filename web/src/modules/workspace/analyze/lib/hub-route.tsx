import { workspacePath } from '@/lib/nav/nav-config.js';

export type OntologyHubTab =
  | 'registry'
  | 'editor'
  | 'health'
  | 'versions'
  | 'statement'
  | 'alignments';

export type AnalyzeHubTab = 'sparql' | 'reasoning';

export const ONTOLOGY_HUB_TABS: OntologyHubTab[] = [
  'registry',
  'editor',
  'health',
  'versions',
  'statement',
  'alignments',
];

export const ANALYZE_HUB_TABS: AnalyzeHubTab[] = ['sparql', 'reasoning'];

export function workspaceOntologyHubPath(
  workspaceId: string,
  tab: OntologyHubTab = 'registry',
  extra?: URLSearchParams,
): string {
  const params = new URLSearchParams(extra);
  if (tab !== 'registry') {
    params.set('tab', tab);
  } else {
    params.delete('tab');
  }
  const q = params.toString();
  return q ? `${workspacePath(workspaceId, 'ontology')}?${q}` : workspacePath(workspaceId, 'ontology');
}

export function workspaceAnalyzeHubPath(workspaceId: string, tab: AnalyzeHubTab = 'sparql'): string {
  if (tab === 'sparql') {
    return workspacePath(workspaceId, 'analyze');
  }
  return `${workspacePath(workspaceId, 'analyze')}?tab=${tab}`;
}
