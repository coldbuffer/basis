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
  /** Class that receives the restriction (subClassOf anonymous restriction). */
  class_uri?: string;
  onProperty?: string;
  /** Filler class for someValuesFrom (legacy key: onClass). */
  filler_class?: string;
  onClass?: string;
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

export function edgeChangeKey(edge: OntologyEdgeChange): string {
  return edge.id ?? `${edge.source}|${edge.type}|${edge.target}`;
}
