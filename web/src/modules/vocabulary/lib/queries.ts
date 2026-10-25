// queries.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useI18n } from '@/i18n/context.js';
import { workspaceOpenApiResponse } from '@/lib/openapi/client.js';
import { parseWsJson } from '@/lib/workspace/ws-api-error.js';
import type { VocabularyScheme, ConceptNode, ImportResponse } from './types';
import {
  useVocabularyWorkspaceId,
  vocabularyApiSuffix,
} from '../components/vocabulary-workspace-context.js';

type VocabularyApiCopy = {
  fetch_schemes_failed: string;
  fetch_hierarchy_failed: string;
  import_failed: string;
};

function useVocabularyApiCopy(): VocabularyApiCopy {
  const { t } = useI18n();
  return t.vocabulary.page.api;
}

const fetchSchemes = async (workspaceId: string, fallback: string): Promise<VocabularyScheme[]> => {
  const res = await workspaceOpenApiResponse('GET', workspaceId, vocabularyApiSuffix('schemes'));
  return parseWsJson<VocabularyScheme[]>(res, fallback);
};

const fetchHierarchy = async (
  workspaceId: string,
  schemeUri: string,
  fallback: string,
): Promise<ConceptNode[]> => {
  const res = await workspaceOpenApiResponse('GET', workspaceId, vocabularyApiSuffix('hierarchy'), {
    params: { query: { scheme: schemeUri } },
  });
  return parseWsJson<ConceptNode[]>(res, fallback);
};

const importVocabulary = async (
  workspaceId: string,
  file: File,
  fallback: string,
): Promise<ImportResponse> => {
  const formData = new FormData();
  formData.append('file', file);
  const res = await workspaceOpenApiResponse('POST', workspaceId, vocabularyApiSuffix('import'), {
    body: formData,
  });
  return parseWsJson<ImportResponse>(res, fallback);
};

export const useVocabularies = () => {
  const workspaceId = useVocabularyWorkspaceId();
  const api = useVocabularyApiCopy();
  return useQuery({
    queryKey: ['vocabularies', workspaceId],
    queryFn: () => fetchSchemes(workspaceId, api.fetch_schemes_failed),
  });
};

export const useConceptHierarchy = (schemeUri: string | undefined) => {
  const workspaceId = useVocabularyWorkspaceId();
  const api = useVocabularyApiCopy();
  return useQuery({
    queryKey: ['hierarchy', workspaceId, schemeUri],
    queryFn: () => fetchHierarchy(workspaceId, schemeUri!, api.fetch_hierarchy_failed),
    enabled: !!schemeUri,
  });
};

export const useImportVocabulary = () => {
  const workspaceId = useVocabularyWorkspaceId();
  const api = useVocabularyApiCopy();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => importVocabulary(workspaceId, file, api.import_failed),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vocabularies', workspaceId] });
      queryClient.invalidateQueries({ queryKey: ['hierarchy', workspaceId] });
    },
  });
};
