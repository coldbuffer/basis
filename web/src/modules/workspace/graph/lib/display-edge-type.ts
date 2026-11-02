/** Human-facing Sigma edge type for explorer labels and filters. */
export function displayGraphEdgeType(
  type: string,
  properties?: Record<string, unknown> | null,
): string {
  const raw = type.trim();
  if (!raw.startsWith('vocabulary_alignment')) {
    return raw || 'related_to';
  }
  const relation = properties?.alignment_relation;
  if (typeof relation === 'string' && relation.trim()) {
    return relation.trim();
  }
  return 'vocabulary_alignment';
}
