import { workspaceOntologyHubPath } from '@/modules/analyze/lib/hub-route.js';

/** Merge search params for vocabulary alignment suggest flow (health panel, review, etc.). */
export function applyVocabularyAlignmentSuggestParams(
  params: URLSearchParams,
  ontologyUri?: string,
): void {
  params.set('tab', 'alignments');
  params.set('alignSuggest', '1');
  const trimmed = ontologyUri?.trim();
  if (trimmed) {
    params.set('alignOntology', trimmed);
  } else {
    params.delete('alignOntology');
  }
}

/** Deep-link to vocabulary alignment tab with suggest dialog open. */
export function vocabularyAlignmentSuggestHref(
  workspaceId: string,
  ontologyUri?: string,
): string {
  const params = new URLSearchParams();
  applyVocabularyAlignmentSuggestParams(params, ontologyUri);
  return workspaceOntologyHubPath(workspaceId, 'alignments', params);
}
