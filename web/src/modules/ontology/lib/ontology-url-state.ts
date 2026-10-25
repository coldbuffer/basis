// Sole owner of the Ontology Hub deep-link query parameters: the names below must not be
// spelled out anywhere else, so that the protocol can change in one place.
const TAB_PARAM = "tab";
const ENTITY_PARAM = "ontologyEntity";
const PROPOSAL_PARAM = "ontologyProposal";
const EDITOR_TAB = "editor";

export interface OntologyUrlState {
  tab?: string;
  entityUri?: string;
  proposalId?: string;
}

/** `undefined` means the parameter is absent; an empty string means it is present but blank. */
export function parseOntologyUrlState(search: string): OntologyUrlState {
  const params = new URLSearchParams(search);
  const rawTab = params.get(TAB_PARAM);
  return {
    tab: rawTab ?? undefined,
    entityUri: params.get(ENTITY_PARAM) ?? undefined,
    proposalId: params.get(PROPOSAL_PARAM) ?? undefined,
  };
}

export function applyTab(search: string, tab: string): string {
  const params = new URLSearchParams(search);
  if (tab === "registry") {
    params.delete(TAB_PARAM);
  } else {
    params.set(TAB_PARAM, tab);
  }
  return `?${params.toString()}`;
}

// A selected entity is only addressable from the editor, so the tab moves with it.
export function applyEntitySelection(search: string, entityUri: string): string {
  const params = new URLSearchParams(search);
  params.set(TAB_PARAM, EDITOR_TAB);
  params.set(ENTITY_PARAM, entityUri);
  return `?${params.toString()}`;
}

// Pairs with applyEntitySelection: an entity URI is resolved back to its owning ontology on
// load, so leaving a stale one behind when the active ontology changes reopens the old ontology.
export function removeEntitySelection(search: string): string {
  const params = new URLSearchParams(search);
  params.delete(ENTITY_PARAM);
  return `?${params.toString()}`;
}

/**
 * Deliberately dual-role, and the argument is what selects the role: given a
 * `search` string this is pure and total, delegating straight to
 * `parseOntologyUrlState`; called with no argument it reads live `window`
 * state and yields empty state if the URL is unreadable. Callers in render or
 * effect paths use the no-argument form; tests and any caller that already
 * holds a search string pass it, which is the only form that is testable.
 */
export function readOntologyUrlState(search?: string): OntologyUrlState {
  if (search !== undefined) {
    return parseOntologyUrlState(search);
  }
  try {
    return parseOntologyUrlState(window.location.search);
  } catch {
    return {};
  }
}

export function applyProposalSelection(search: string, proposalId: string): string {
  const params = new URLSearchParams(search);
  params.set(TAB_PARAM, "versions");
  params.set(PROPOSAL_PARAM, proposalId);
  return `?${params.toString()}`;
}

export function hasOntologyUrlState(search?: string): boolean {
  const { tab, entityUri, proposalId } = readOntologyUrlState(search);
  return tab !== undefined || entityUri !== undefined || proposalId !== undefined;
}

function updateSearch(transform: (search: string) => string): void {
  try {
    window.history.replaceState(
      null,
      "",
      `${transform(window.location.search)}${window.location.hash}`,
    );
  } catch {
    // Deep-link state is a convenience; every caller stays correct without it.
  }
}

export function writeTab(tab: string): void {
  updateSearch((search) => applyTab(search, tab));
}

export function writeEntitySelection(entityUri: string): void {
  updateSearch((search) => applyEntitySelection(search, entityUri));
}

export function clearEntitySelection(): void {
  updateSearch(removeEntitySelection);
}

export function writeProposalSelection(proposalId: string): void {
  updateSearch((search) => applyProposalSelection(search, proposalId));
}
