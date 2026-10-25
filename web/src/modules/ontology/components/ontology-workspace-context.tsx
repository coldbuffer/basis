import { createContext, useContext, type ReactNode } from "react";

import { localeFromBrowser } from "@/i18n/locale.js";
import { messagesForLocale } from "@/i18n/pick-locale.js";

import { workspaceApiPath } from '@/lib/openapi/client.js';

const OntologyWorkspaceCatalogContext = createContext<string | null>(null);

export function OntologyWorkspaceCatalogProvider({
  workspaceId,
  children,
}: {
  workspaceId: string;
  children: ReactNode;
}) {
  return (
    <OntologyWorkspaceCatalogContext.Provider value={workspaceId}>{children}</OntologyWorkspaceCatalogContext.Provider>
  );
}

export function useOntologyWorkspaceId(): string {
  const workspaceId = useContext(OntologyWorkspaceCatalogContext);
  if (!workspaceId) {
    const lang = typeof navigator !== "undefined" ? navigator.language : "en";
    throw new Error(messagesForLocale(localeFromBrowser(lang)).ontology.page.workspace_required);
  }
  return workspaceId;
}

/** OpenAPI suffix under `ontology/…`. */
export function ontologyApiSuffix(suffix: string): string {
  return `ontology/${suffix.replace(/^\//, "")}`;
}

/** OpenAPI suffix under `vocabulary/…`. */
export function vocabularyApiSuffix(suffix: string): string {
  return `vocabulary/${suffix.replace(/^\//, "")}`;
}

/** Absolute API path for links/debug (`/api/v1/workspaces/{id}/ontology/…`). */
export function ontologyPath(workspaceId: string, suffix: string, query?: string): string {
  const path = workspaceApiPath(workspaceId, ontologyApiSuffix(suffix));
  return query ? `${path}?${query}` : path;
}

/** Absolute API path for vocabulary routes. */
export function vocabularyPath(workspaceId: string, suffix: string, query?: string): string {
  const path = workspaceApiPath(workspaceId, vocabularyApiSuffix(suffix));
  return query ? `${path}?${query}` : path;
}
