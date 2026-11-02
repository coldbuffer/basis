import { workspacePath } from '@/lib/nav/nav-config.js';

const JOB_PARAM = 'job';
const FILTER_PARAM = 'filter';

export type ProcessingUrlFilter = 'all' | 'active' | 'failed' | 'succeeded';

const PROCESSING_URL_FILTERS = new Set<ProcessingUrlFilter>([
  'all',
  'active',
  'failed',
  'succeeded',
]);

export function parseProcessingUrlState(search: string): {
  jobId?: string;
  filter?: ProcessingUrlFilter;
} {
  const params = new URLSearchParams(search);
  const jobId = params.get(JOB_PARAM)?.trim();
  const rawFilter = params.get(FILTER_PARAM)?.trim();
  const filter =
    rawFilter && PROCESSING_URL_FILTERS.has(rawFilter as ProcessingUrlFilter)
      ? (rawFilter as ProcessingUrlFilter)
      : undefined;
  return { jobId: jobId || undefined, filter };
}

export function processingPath(
  workspaceId: string,
  opts?: { jobId?: string; filter?: ProcessingUrlFilter },
): string {
  const params = new URLSearchParams();
  if (opts?.filter && opts.filter !== 'all') {
    params.set(FILTER_PARAM, opts.filter);
  }
  if (opts?.jobId?.trim()) {
    params.set(JOB_PARAM, opts.jobId.trim());
  }
  const q = params.toString();
  return q ? `${workspacePath(workspaceId, 'processing')}?${q}` : workspacePath(workspaceId, 'processing');
}

/** Deep-link to processing jobs with a specific job expanded (F-SRC-08). */
export function processingJobPath(workspaceId: string, jobId: string): string {
  return processingPath(workspaceId, { jobId });
}
