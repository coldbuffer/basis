export type ProcessingStartOptions = {
  chunk?: boolean;
  chunk_method?: string;
  chunk_size?: number;
  chunk_overlap?: number;
  extract?: boolean;
  ner_method?: string;
  ner_model?: string;
  llm_model?: string;
  llm_endpoint_id?: string;
  relation_method?: string;
  extract_relations?: boolean;
};

function stableHash(input: string): string {
  let hash = 0;
  for (let i = 0; i < input.length; i += 1) {
    hash = (hash * 31 + input.charCodeAt(i)) | 0;
  }
  return Math.abs(hash).toString(36);
}

/** Workspace-scoped idempotency key for `POST .../processing/jobs` (safe retries / double-submit). */
export function processingStartIdempotencyKey(
  versionId: string,
  options?: ProcessingStartOptions,
): string {
  if (!options) {
    return `ingest-start:${versionId}`;
  }
  const payload = JSON.stringify({
    chunk: options.chunk,
    chunk_method: options.chunk_method,
    chunk_size: options.chunk_size,
    chunk_overlap: options.chunk_overlap,
    extract: options.extract,
    ner_method: options.ner_method,
    llm_model: options.llm_model,
    llm_endpoint_id: options.llm_endpoint_id,
    relation_method: options.relation_method,
    extract_relations: options.extract_relations,
  });
  return `ingest-config:${versionId}:${stableHash(payload)}`;
}
