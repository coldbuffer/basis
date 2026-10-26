import { workspaceOntologyHubPath } from '@/modules/analyze/lib/hub-route.js';

/** Deep-link to semantic alignment with the create type-mapping dialog prefilled. */
export function statementTypeMappingHref(
  workspaceId: string,
  options: { label: string; targetUri?: string | null },
): string {
  const label = options.label.trim();
  const params = new URLSearchParams();
  if (label) {
    params.set('typeMappingLabel', label);
  }
  const uri = options.targetUri?.trim();
  if (uri) {
    params.set('typeMappingUri', uri);
  }
  return workspaceOntologyHubPath(workspaceId, 'statement', params);
}
