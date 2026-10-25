import { fmt } from "@/i18n/format.js";
import type { Locale } from "@/i18n/locale.js";
import { messagesForLocale } from "@/i18n/pick-locale.js";

import { parseWsJson, wsMutationResult } from '@/lib/workspace/ws-api-error';
import {
  workspaceOpenApiDELETE,
  workspaceOpenApiGET,
  workspaceOpenApiPATCH,
  workspaceOpenApiPOST,
  workspaceOpenApiResponse,
} from '@/lib/openapi/client.js';
import type { OntologyEditorDraftDiff } from './ontology-editor-draft.js';
import { ontologyApiSuffix } from '../components/ontology-workspace-context.js';
import type {
  AlignmentRelation,
  AlignmentSuggestion,
  OntologyAlignment,
  OntologyEntry,
  OntologyHealthResponse,
  ShaclGenerateResponse,
  ShaclShapesResponse,
  ShaclValidationResponse,
} from "./types";

export type OntologyGraphNode = {
  id: string;
  type: string;
  entity_type: string;
  content?: string;
  properties?: Record<string, unknown>;
};

export type OntologyGraphEdge = {
  id?: string;
  source: string;
  target: string;
  type: string;
  weight?: number;
  properties?: Record<string, unknown>;
};

export type OntologyGraphResponse = {
  uri: string;
  nodes: OntologyGraphNode[];
  edges: OntologyGraphEdge[];
};

export type OntologyEntityOwner = {
  owning_ontology?: string | null;
};

export type OntologyRequestOptions = {
  locale?: Locale;
};

export type OntologyGraphRequestOptions = OntologyRequestOptions & {
  signal?: AbortSignal;
};

async function parseResponse<T>(response: Response, locale: Locale = "en"): Promise<T> {
  const common = messagesForLocale(locale).core.common;
  const data = await parseWsJson<T & { message?: string }>(
    response,
    fmt(common.requestFailedStatus, { status: response.status }),
  );
  if (response.status === 207) {
    console.warn(data.message?.trim() || common.partialSuccess);
  }
  return data as T;
}

export async function loadOntologyRegistry(
  workspaceId: string,
  options?: OntologyRequestOptions,
): Promise<OntologyEntry[]> {
  return workspaceOpenApiGET<OntologyEntry[]>(workspaceId, ontologyApiSuffix("registry"));
}

export async function loadOntologyGraph(
  workspaceId: string,
  uri: string,
  options?: OntologyGraphRequestOptions,
): Promise<OntologyGraphResponse> {
  const response = await workspaceOpenApiResponse('GET', workspaceId, ontologyApiSuffix("graph"), {
    signal: options?.signal,
    params: { query: { uri } },
  });
  return parseResponse<OntologyGraphResponse>(response, options?.locale);
}

export type OntologyOwnerVerdict = string | null | undefined;

export async function loadOntologyEntityOwner(
  workspaceId: string,
  uri: string,
): Promise<OntologyOwnerVerdict> {
  try {
    const owner = await workspaceOpenApiGET<OntologyEntityOwner>(
      workspaceId,
      ontologyApiSuffix(`entity/${encodeURIComponent(uri)}`),
    );
    const verdict = owner?.owning_ontology;
    return verdict === undefined ? undefined : verdict;
  } catch {
    return undefined;
  }
}

export async function loadAlignments(
  workspaceId: string,
  uri?: string,
  options?: OntologyRequestOptions,
): Promise<OntologyAlignment[]> {
  return workspaceOpenApiGET<OntologyAlignment[]>(workspaceId, ontologyApiSuffix("alignments"), {
    params: uri ? { query: { uri } } : undefined,
  });
}

export async function saveAlignment(
  workspaceId: string,
  payload: {
    source_uri: string;
    target_uri: string;
    relation: AlignmentRelation;
    confidence: number;
    provenance?: string;
    source?: string;
    reviewer?: string;
  },
  options?: OntologyRequestOptions,
): Promise<OntologyAlignment> {
  const response = await workspaceOpenApiResponse('POST', workspaceId, ontologyApiSuffix("alignments"), {
    body: payload,
  });
  return parseResponse<OntologyAlignment>(response, options?.locale);
}

export async function removeAlignment(
  workspaceId: string,
  id: string,
  options?: OntologyRequestOptions,
): Promise<void> {
  await workspaceOpenApiDELETE(workspaceId, ontologyApiSuffix("alignments"), {
    params: { query: { id } },
  });
}

export async function suggestAlignments(
  workspaceId: string,
  payload: {
    source_ontology_uri?: string;
    target_ontology_uri?: string;
    threshold: number;
    limit: number;
  },
  options?: OntologyRequestOptions,
): Promise<AlignmentSuggestion[]> {
  const response = await workspaceOpenApiResponse('POST', workspaceId, ontologyApiSuffix("suggest-alignments"), {
    body: payload,
  });
  return parseResponse<AlignmentSuggestion[]>(response, options?.locale);
}

export async function loadOntologyHealth(
  workspaceId: string,
  uri: string,
  options?: OntologyRequestOptions,
): Promise<OntologyHealthResponse> {
  const response = await workspaceOpenApiResponse('GET', workspaceId, ontologyApiSuffix("health"), {
    params: { query: { uri } },
  });
  return parseResponse<OntologyHealthResponse>(response, options?.locale);
}

export async function generateShacl(
  workspaceId: string,
  uri: string,
  qualityTier: "standard" | "strict" = "strict",
  options?: OntologyRequestOptions,
): Promise<ShaclGenerateResponse> {
  const response = await workspaceOpenApiResponse('POST', workspaceId, ontologyApiSuffix("shacl/generate"), {
    body: { uri, quality_tier: qualityTier },
  });
  return parseResponse<ShaclGenerateResponse>(response, options?.locale);
}

export async function loadShaclShapes(
  workspaceId: string,
  uri: string,
  options?: OntologyRequestOptions,
): Promise<ShaclShapesResponse> {
  const response = await workspaceOpenApiResponse('GET', workspaceId, ontologyApiSuffix("shacl/shapes"), {
    params: { query: { uri } },
  });
  return parseResponse<ShaclShapesResponse>(response, options?.locale);
}

export async function validateShacl(
  workspaceId: string,
  uri: string,
  shaclTurtle: string,
  options?: OntologyRequestOptions,
): Promise<ShaclValidationResponse> {
  const response = await workspaceOpenApiResponse('POST', workspaceId, ontologyApiSuffix("shacl/validate"), {
    body: { uri, shacl_turtle: shaclTurtle },
  });
  return parseResponse<ShaclValidationResponse>(response, options?.locale);
}

export async function saveGovernanceShacl(
  workspaceId: string,
  ontologyUri: string,
  shaclTurtle: string,
  options?: OntologyRequestOptions,
): Promise<{ config: { governance_ontology_uri?: string | null; governance_shacl_turtle?: string | null } }> {
  const response = await workspaceOpenApiResponse('PUT', workspaceId, 'governance/shacl', {
    body: { ontology_uri: ontologyUri, shacl_turtle: shaclTurtle },
  });
  return parseResponse(response, options?.locale);
}

export type OntologyDraftSaveResult = { draft_id: string };

export type OntologyProposalSubmitResult = { proposal_id: string };

export async function saveOntologyDraft(
  workspaceId: string,
  payload: {
    ontology_uri: string;
    diff: OntologyEditorDraftDiff;
    author: string;
    summary?: string;
  },
  options?: OntologyRequestOptions,
): Promise<OntologyDraftSaveResult> {
  const response = await workspaceOpenApiPATCH<OntologyDraftSaveResult>(
    workspaceId,
    ontologyApiSuffix('draft'),
    { body: payload },
  );
  return response;
}

export async function submitOntologyProposal(
  workspaceId: string,
  payload: {
    draft_id: string;
    ontology_uri: string;
    summary: string;
    reviewer?: string | null;
  },
  options?: OntologyRequestOptions,
): Promise<OntologyProposalSubmitResult> {
  const response = await workspaceOpenApiPOST<OntologyProposalSubmitResult>(
    workspaceId,
    ontologyApiSuffix('propose'),
    { body: payload },
  );
  return response;
}

export { wsMutationResult };
