import { createContext, useContext, type ReactNode } from "react";

import { localeFromBrowser } from "@/i18n/locale.js";
import { messagesForLocale } from "@/i18n/pick-locale.js";

import {
  vocabularyApiSuffix,
  vocabularyPath as buildVocabularyPath,
} from "@/modules/ontology/components/ontology-workspace-context.js";

export { vocabularyApiSuffix };

const VocabularyWorkspaceCatalogContext = createContext<string | null>(null);

export function VocabularyWorkspaceCatalogProvider({
  workspaceId,
  children,
}: {
  workspaceId: string;
  children: ReactNode;
}) {
  return (
    <VocabularyWorkspaceCatalogContext.Provider value={workspaceId}>{children}</VocabularyWorkspaceCatalogContext.Provider>
  );
}

export function useVocabularyWorkspaceId(): string {
  const workspaceId = useContext(VocabularyWorkspaceCatalogContext);
  if (!workspaceId) {
    const lang = typeof navigator !== "undefined" ? navigator.language : "en";
    throw new Error(messagesForLocale(localeFromBrowser(lang)).vocabulary.page.workspace_required);
  }
  return workspaceId;
}

export function vocabularyPath(workspaceId: string, suffix: string, query?: string): string {
  return buildVocabularyPath(workspaceId, suffix, query);
}
