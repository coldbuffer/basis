import { workspaceConnectorHomePath } from '@/lib/nav/nav-config.js';

export function workspaceConnectorsAuthorizationHref(
  workspaceId: string,
  opts?: { subjectId?: string; service?: string },
): string {
  const params = new URLSearchParams({ section: 'authorization' });
  const subjectId = opts?.subjectId?.trim();
  const service = opts?.service?.trim();
  if (subjectId) {
    params.set('subject_id', subjectId);
  }
  if (service) {
    params.set('service', service);
  }
  return `${workspaceConnectorHomePath(workspaceId)}?${params.toString()}`;
}
