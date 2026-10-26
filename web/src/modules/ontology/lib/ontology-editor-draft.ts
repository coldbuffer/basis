/** Draft diff shape aligned with API `DraftDiff`. */

export type OntologyEdgeChange = {
  source: string;
  target: string;
  type: string;
  id?: string;
};

export type OntologyAxiomChange = {
  type: string;
  subject?: string;
  object?: string;
  value?: string;
};

export type OntologyRestrictionChange = {
  type: string;
  /** `object` (default) or `data` — OWL 2 property scope. */
  property_scope?: 'object' | 'data';
  /** Class that receives the restriction (subClassOf anonymous restriction). */
  class_uri?: string;
  onProperty?: string;
  /** Filler class for someValuesFrom / allValuesFrom / qualified (legacy: onClass). */
  filler_class?: string;
  onClass?: string;
  /** Object ``hasValue`` individual URI. */
  filler_individual?: string;
  /** Data range or literal datatype IRI. */
  filler_datatype?: string;
  /** Data ``hasValue`` lexical form. */
  literal_value?: string;
  /** Cardinality for min/max/exact (qualified or unqualified). */
  cardinality?: number;
  value?: string;
};

export type OntologyEditorDraftDiff = {
  added_classes: string[];
  removed_classes: string[];
  modified_classes: Record<string, Record<string, unknown>>;
  added_properties: string[];
  removed_properties: string[];
  modified_properties: Record<string, Record<string, unknown>>;
  added_individuals: string[];
  removed_individuals: string[];
  added_edges: OntologyEdgeChange[];
  removed_edges: string[];
  added_restrictions: OntologyRestrictionChange[];
  removed_restrictions: OntologyRestrictionChange[];
  added_axioms: OntologyAxiomChange[];
  removed_axioms: OntologyAxiomChange[];
  annotation_changes: Record<string, Record<string, unknown>>;
};

export function createEmptyOntologyEditorDraft(): OntologyEditorDraftDiff {
  return {
    added_classes: [],
    removed_classes: [],
    modified_classes: {},
    added_properties: [],
    removed_properties: [],
    modified_properties: {},
    added_individuals: [],
    removed_individuals: [],
    added_edges: [],
    removed_edges: [],
    added_restrictions: [],
    removed_restrictions: [],
    added_axioms: [],
    removed_axioms: [],
    annotation_changes: {},
  };
}

/** Namespace stem for new entity URIs (`http://ex.org/foo#ontology` → `http://ex.org/foo`). */
export function ontologyEntityNamespace(ontologyUri: string): string {
  const trimmed = ontologyUri.trim().replace(/[#/]+$/, '');
  if (trimmed.endsWith('#ontology')) {
    return trimmed.slice(0, -'#ontology'.length).replace(/[#/]+$/, '');
  }
  return trimmed;
}

export function allocateOntologyEntityUri(namespaceStem: string, localName: string): string {
  const safe = localName.trim().replace(/\s+/g, '_').replace(/[^\w.-]/g, '_') || 'Term';
  const base = namespaceStem.replace(/[#/]+$/, '');
  return `${base}/${safe}`;
}

export function labelFromEntityUri(uri: string): string {
  const fragment = uri.split('#').pop() ?? uri;
  const segment = fragment.split('/').pop() ?? fragment;
  return segment || uri;
}

export function edgeTripleKey(edge: Pick<OntologyEdgeChange, 'source' | 'type' | 'target'>): string {
  return `${edge.source}|${edge.type}|${edge.target}`;
}

export function edgeChangeKey(edge: OntologyEdgeChange): string {
  return edge.id ?? edgeTripleKey(edge);
}

/** Reference stored in ``removed_edges`` when no stable runtime edge id exists. */
export function edgeRemovalRef(
  edge: Pick<OntologyEdgeChange, 'source' | 'type' | 'target'> & { id?: string },
): string {
  const id = edge.id?.trim();
  return id ? id : edgeTripleKey(edge);
}
