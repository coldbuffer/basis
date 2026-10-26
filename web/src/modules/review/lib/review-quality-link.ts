import { workspaceQualityPath } from '@/lib/nav/nav-config.js';
import { workspaceOntologyHubPath } from '@/modules/analyze/lib/hub-route.js';
import { statementTypeMappingHref } from '@/modules/mappings/lib/statement-type-mapping-link.js';

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
    return workspaceOntologyHubPath(workspaceId, 'statement');
  }
  if (kind === 'low_confidence') {
    return workspaceOntologyHubPath(workspaceId, 'statement');
  }
  if (kind === 'vocabulary_alignment_change') {
    const ontologyUri = String(payload.source_uri ?? '').trim();
    const hashIdx = ontologyUri.lastIndexOf('#');
    const slashIdx = ontologyUri.lastIndexOf('/');
    const stem =
      hashIdx > 0
        ? ontologyUri.substring(0, hashIdx)
        : slashIdx > 0
          ? ontologyUri.substring(0, slashIdx)
          : '';
    const params = new URLSearchParams();
    if (stem) params.set('alignOntology', stem);
    return workspaceOntologyHubPath(workspaceId, 'alignments', params);
  }
  if (kind === 'unmapped_entity_type') {
    const label = String(payload.label ?? '').trim();
    if (!label) {
      return workspaceOntologyHubPath(workspaceId, 'statement');
    }
    const suggestions = payload.vocabulary_alignment_suggestions;
    const firstUri =
      Array.isArray(suggestions) &&
      suggestions[0] &&
      typeof suggestions[0] === 'object' &&
      suggestions[0] !== null &&
      typeof (suggestions[0] as { uri?: string }).uri === 'string'
        ? (suggestions[0] as { uri: string }).uri
        : undefined;
    return statementTypeMappingHref(workspaceId, { label, targetUri: firstUri });
  }
  return null;
}

export function reviewItemQualityLinkLabelKey(
  kind: string,
  payload: Record<string, unknown>,
):
  | 'open_data_quality_structure'
  | 'open_statement_mappings'
  | 'open_create_type_mapping'
  | 'open_vocabulary_alignments'
  | null {
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
  if (kind === 'unmapped_entity_type') {
    return 'open_create_type_mapping';
  }
  if (kind === 'vocabulary_alignment_change') {
    return 'open_vocabulary_alignments';
  }
  return null;
}
