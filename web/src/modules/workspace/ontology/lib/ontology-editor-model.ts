export type EditorEntityType = "ontology" | "class" | "property" | "external";

export type RegistryEntry = {
  uri: string;
  name: string;
};

/** React Flow MiniMap needs literal colors; keep neutral — canvas uses app `background`. */
export const ONTOLOGY_MINIMAP_THEME = {
  bgColor: "transparent",
  maskColor: "rgba(0, 0, 0, 0.4)",
  maskStrokeColor: "var(--primary)",
  maskStrokeWidth: 2,
  nodeColor: "var(--primary)",
  nodeStrokeColor: "var(--border)",
  nodeStrokeWidth: 1,
  style: {
    border: "1px solid var(--border)",
    borderRadius: 6,
    boxShadow: "var(--shadow)",
  },
} as const;

// Last-resort guess, reached only when the backend gave no verdict: it has no
// notion of nested vocabularies, so it can name a parent that does not contain
// the entity. Authority is owning_ontology from workspace ontology entity API.
// Aligns with server resolve_owning_ontology (basis/domain/explorer/ontology_graph_scope.py).
function ownsByNamespace(entityUri: string, ontologyUri: string): boolean {
  const stem = ontologyUri.replace(/[/#]+$/, "");
  return entityUri === ontologyUri
    || entityUri.startsWith(`${stem}#`)
    || entityUri.startsWith(`${stem}/`);
}

/**
 * Three outcomes, deliberately not collapsed into `string | undefined`.
 *
 * `unowned` and `unresolved` both yield "no ontology to open", but they must
 * not be treated alike: a caller that writes `resolve(...) || entries[0]` turns
 * the backend's authoritative "nothing owns this entity" into "open an
 * arbitrary ontology", which reintroduces the parent-selection bug this whole
 * verdict exists to prevent. The union makes that collapse a type error.
 */
export type EditorOntologyResolution =
  | { status: "resolved"; uri: string }
  | { status: "unowned"; entityUri: string }
  | { status: "unresolved" };

// Picks the registered ontology to open for a deep-linked entity. A null
// verdict is the backend's authoritative "nothing owns this entity": the
// namespace guess must stay suppressed, or an unregistered nested namespace
// would select its registered parent again. Only an unavailable verdict
// (undefined) may fall back to inference.
export function resolveEditorOntology(
  entries: RegistryEntry[],
  entityUri: string,
  ownerVerdict: string | null | undefined,
): EditorOntologyResolution {
  if (ownerVerdict === null) {
    return { status: "unowned", entityUri };
  }
  const uri = inferOntologyUri(entries, entityUri, ownerVerdict);
  return uri === undefined ? { status: "unresolved" } : { status: "resolved", uri };
}

// Picks the registered ontology to open for an entity: the backend-resolved
// explicitOwner wins outright, the namespace guess is only the fallback.
export function inferOntologyUri(
  entries: RegistryEntry[],
  entityUri: string,
  explicitOwner?: string,
): string | undefined {
  // Trusted even when the registry does not list it. Falling through to the
  // namespace guess here would answer a question nobody asked — the backend
  // named this entity's owner, and silently opening a *different* ontology is
  // worse than opening one the registry has not been told about yet, which
  // surfaces as an explicit error from the workspace ontology graph API.
  if (explicitOwner) {
    return explicitOwner;
  }
  return [...entries]
    .filter((entry) => ownsByNamespace(entityUri, entry.uri))
    .sort((left, right) => right.uri.length - left.uri.length)[0]?.uri;
}

export function isEditableEntityType(entityType?: EditorEntityType): boolean {
  return entityType === "class" || entityType === "property";
}
