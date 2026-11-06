import type { LocaleMessages } from '@/i18n/en.js';

export type ProcessingJob = {
  id: string;
  version_id: string;
  doc_id: string;
  document_title: string;
  status: string;
  version_status: string;
  attempt: number;
  error_code: string | null;
  error_detail?: { message?: string } | null;
  options: Record<string, unknown>;
  created_at: string;
  progress?: number | null;
  result?: {
    checkpoint?: {
      completed_chunk_ids?: string[];
      chunk_count?: number;
    };
  } | null;
};

const PROCESSING_STATUSES = new Set([
  'queued',
  'running',
  'parsing',
  'chunking',
  'embedding',
  'extracting',
]);

export function statusIsProcessing(status: string | null | undefined): boolean {
  return status != null && PROCESSING_STATUSES.has(status);
}

export function processingJobStatusLabel(
  status: string | null | undefined,
  labels: LocaleMessages['library']['sources']['job_status'],
  emptyCell: string,
): string {
  if (!status) return emptyCell;
  const key = status as keyof typeof labels;
  return key in labels ? labels[key] : status;
}

export function jobIsActive(status: string): boolean {
  return statusIsProcessing(status);
}

/** Queued, running, and paused jobs stay on the in-progress filter. */
export function jobInActiveFilter(status: string): boolean {
  return jobIsActive(status) || status === 'paused';
}

export function ingestCheckpoint(job: {
  result?: ProcessingJob['result'];
}): { done: number; total: number } | null {
  const checkpoint = job.result?.checkpoint;
  const ids = checkpoint?.completed_chunk_ids;
  const total = checkpoint?.chunk_count;
  if (!Array.isArray(ids) || typeof total !== 'number' || total <= 0) return null;
  return { done: ids.length, total };
}

export function sortProcessingJobs(jobs: ProcessingJob[]): ProcessingJob[] {
  return [...jobs].sort((a, b) => {
    const ta = Date.parse(a.created_at) || 0;
    const tb = Date.parse(b.created_at) || 0;
    return tb - ta;
  });
}
