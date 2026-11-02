import { workspacePath } from '@/lib/nav/nav-config.js';

const DOC_PARAM = 'doc';
const VERSION_PARAM = 'version';
const PROCESS_PARAM = 'process';

export function parseSourcesUrlState(search: string): {
  docId?: string;
  versionId?: string;
  openProcessDialog: boolean;
} {
  const params = new URLSearchParams(search);
  const docId = params.get(DOC_PARAM)?.trim();
  const versionId = params.get(VERSION_PARAM)?.trim();
  return {
    docId: docId || undefined,
    versionId: versionId || undefined,
    openProcessDialog: params.get(PROCESS_PARAM) === '1' && Boolean(versionId),
  };
}

/** Highlight a document row on the sources library (F-SRC-08). */
export function sourcesDocumentPath(workspaceId: string, docId: string): string {
  const params = new URLSearchParams({ [DOC_PARAM]: docId });
  return `${workspacePath(workspaceId, 'sources')}?${params.toString()}`;
}

/** Open the process dialog for a version (chunk/extract). */
export function sourcesProcessPath(workspaceId: string, versionId: string): string {
  const params = new URLSearchParams({
    [VERSION_PARAM]: versionId,
    [PROCESS_PARAM]: '1',
  });
  return `${workspacePath(workspaceId, 'sources')}?${params.toString()}`;
}
