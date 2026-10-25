import { workspacePath, workspaceQualityPath } from '@/lib/nav/nav-config.js';

type ShaclPayload = {
  detector?: string;
  rule_id?: string;
  ontology_uri?: string;
};

/** Deep-link from a review item to the right data-quality or mappings surface. */
export function reviewItemQualityHref(
  workspaceId: string,
  kind: string,
  payload: Record<string, unknown>,
): string | null {
  if (kind === 'shacl_violation') {
    const shacl = payload as ShaclPayload;
    if (shacl.detector === 'l3_hub_shacl' || shacl.rule_id === 'hub:shacl') {
      return workspaceQualityPath(workspaceId, 'structure', {
        ontology_uri: shacl.ontology_uri,
      });
    }
    return workspacePath(workspaceId, 'mappings');
  }
  if (kind === 'low_confidence') {
    return workspacePath(workspaceId, 'mappings');
  }
  return null;
}

export function reviewItemQualityLinkLabelKey(
  kind: string,
  payload: Record<string, unknown>,
): 'open_data_quality_structure' | 'open_statement_mappings' | null {
  if (kind === 'shacl_violation') {
    const shacl = payload as ShaclPayload;
    if (shacl.detector === 'l3_hub_shacl' || shacl.rule_id === 'hub:shacl') {
      return 'open_data_quality_structure';
    }
    return 'open_statement_mappings';
  }
  if (kind === 'low_confidence') {
    return 'open_statement_mappings';
  }
  return null;
}
