type OntologyAlignmentRow = {
  source_uri: string;
  target_uri: string;
  source_label?: string | null;
  target_label?: string | null;
  relation: string;
};

const CLASS_ALIGNMENT_RELATIONS = new Set([
  'owl:equivalentClass',
  'skos:exactMatch',
  'skos:closeMatch',
  'skos:broadMatch',
  'skos:narrowMatch',
  'skos:relatedMatch',
]);

const PROPERTY_ALIGNMENT_RELATIONS = new Set(['owl:equivalentProperty']);

export type VocabularyAlignmentPickerHit = {
  uri: string;
  label: string;
  fromVocabularyAlignment: true;
};

function relationAllowed(entityType: 'class' | 'property', relation: string): boolean {
  if (entityType === 'class') {
    return CLASS_ALIGNMENT_RELATIONS.has(relation);
  }
  return PROPERTY_ALIGNMENT_RELATIONS.has(relation);
}

function matchesQuery(text: string, query: string): boolean {
  return text.toLowerCase().includes(query.toLowerCase());
}

/** Map vocabulary-alignment rows to URI picker hits matching the search query. */
export function vocabularyAlignmentPickerHits(
  alignments: OntologyAlignmentRow[],
  entityType: 'class' | 'property',
  query: string,
): VocabularyAlignmentPickerHit[] {
  const q = query.trim();
  if (!q) {
    return [];
  }
  const seen = new Set<string>();
  const hits: VocabularyAlignmentPickerHit[] = [];
  for (const row of alignments) {
    if (!relationAllowed(entityType, row.relation)) {
      continue;
    }
    const sides = [
      { uri: row.source_uri, label: row.source_label?.trim() || row.source_uri },
      { uri: row.target_uri, label: row.target_label?.trim() || row.target_uri },
    ];
    for (const side of sides) {
      if (!side.uri || seen.has(side.uri)) {
        continue;
      }
      if (!matchesQuery(side.label, q) && !matchesQuery(side.uri, q)) {
        continue;
      }
      seen.add(side.uri);
      hits.push({ uri: side.uri, label: side.label, fromVocabularyAlignment: true });
    }
  }
  return hits;
}
