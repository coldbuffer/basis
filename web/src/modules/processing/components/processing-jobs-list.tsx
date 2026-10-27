import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { DataTable, type DataTableColumn } from '@/components/app/shared/console/DataTable.js';
import { Badge } from '@/components/ui/badge.js';
import { Button } from '@/components/ui/button.js';
import { Spinner } from '@/components/ui/spinner.js';
import { useI18n } from '@/i18n/context.js';
import { fmt, formatLocaleDateTime, formatLocaleNumber } from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import { messageForApiErrorCode } from '@/lib/errors/api-error-message.js';
import {
  type ProcessingJob,
  jobIsActive,
  processingJobStatusLabel,
  statusIsProcessing,
} from '@/modules/processing/lib/processing-job.js';
import { ProcessingOptionsSnapshot } from '@/components/app/shared/workspace/processing-options-snapshot.js';
import { workspaceAlertsPath, processingAlertEpisodeKey } from '@/modules/alerts/lib/alerts-url.js';
import { workspacePath } from '@/lib/nav/nav-config.js';
import { sourcesDocumentPath } from '@/modules/library/lib/sources-url-state.js';
import { cn } from '@/lib/utils.js';

export type ProcessingJobFilter = 'all' | 'active' | 'failed' | 'succeeded';

function jobStatusBadgeProps(status: string): {
  variant: 'destructive' | 'outline' | 'secondary';
  className?: string;
} {
  if (status === 'failed') return { variant: 'destructive' };
  if (status === 'succeeded') return { variant: 'outline', className: 'badge-status-success' };
  if (statusIsProcessing(status)) {
    return { variant: 'outline', className: 'badge-status-warning' };
  }
  return { variant: 'secondary' };
}

export function filterProcessingJobs(
  jobs: ProcessingJob[],
  query: string,
  filter: ProcessingJobFilter,
): ProcessingJob[] {
  const q = query.trim().toLowerCase();
  return jobs.filter((job) => {
    if (filter === 'active' && !jobIsActive(job.status)) return false;
    if (filter === 'failed' && job.status !== 'failed') return false;
    if (filter === 'succeeded' && job.status !== 'succeeded') return false;
    if (!q) return true;
    return (
      job.id.toLowerCase().includes(q) ||
      job.doc_id.toLowerCase().includes(q) ||
      (job.document_title ?? '').toLowerCase().includes(q)
    );
  });
}

export function ProcessingJobsList({
  workspaceId,
  jobs,
  jobFocusId,
  canEdit,
  busyVersionId,
  graphEnabled,
  search,
  filter,
  onRetry,
  onCopyLink,
}: {
  workspaceId: string;
  jobs: ProcessingJob[];
  jobFocusId?: string;
  canEdit: boolean;
  busyVersionId: string | null;
  graphEnabled: boolean;
  search: string;
  filter: ProcessingJobFilter;
  onRetry: (job: ProcessingJob) => void;
  onCopyLink: (jobId: string) => void;
}) {
  const { t, locale } = useI18n();
  const k = t.library.sources;
  const p = t.processing.jobs;
  const emptyCell = t.core.common.emptyCell;

  const filtered = useMemo(
    () => filterProcessingJobs(jobs, search, filter),
    [filter, jobs, search],
  );

  const [expandedId, setExpandedId] = useState<string | null>(jobFocusId ?? null);

  useEffect(() => {
    if (jobFocusId) setExpandedId(jobFocusId);
  }, [jobFocusId]);

  useEffect(() => {
    if (!jobFocusId) return;
    const el = document.getElementById(`processing-job-row-${jobFocusId}`);
    el?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [jobFocusId, filtered]);

  const graphFocusPath = (docId: string) =>
    `${workspacePath(workspaceId, 'graph')}?focus=${encodeURIComponent(docId)}`;

  const columns = useMemo<DataTableColumn<ProcessingJob>[]>(
    () => [
      {
        key: 'document',
        header: p.col_document,
        render: (job) => (
          <div className="min-w-0 space-y-0.5">
            <p className="truncate font-medium text-foreground">
              {job.document_title || job.doc_id}
            </p>
            <p className="truncate font-mono text-xs text-muted-foreground">{job.doc_id}</p>
          </div>
        ),
      },
      {
        key: 'status',
        header: p.col_status,
        width: '8.5rem',
        render: (job) => {
          const badge = jobStatusBadgeProps(job.status);
          return (
            <Badge variant={badge.variant} className={cn('gap-1 font-normal', badge.className)}>
              {statusIsProcessing(job.status) ? (
                <Spinner className="size-3 shrink-0" />
              ) : null}
              {processingJobStatusLabel(job.status, k.job_status, emptyCell)}
            </Badge>
          );
        },
      },
      {
        key: 'attempt',
        header: p.col_attempt,
        hideBelow: 'sm',
        width: '5.5rem',
        render: (job) =>
          fmt(k.history_attempt, {
            attempt: formatLocaleNumber(locale as Locale, job.attempt),
          }),
      },
      {
        key: 'created',
        header: p.col_created,
        hideBelow: 'md',
        width: '10.5rem',
        render: (job) =>
          job.created_at
            ? formatLocaleDateTime(locale as Locale, job.created_at)
            : emptyCell,
      },
      {
        key: 'actions',
        header: p.col_actions,
        align: 'right',
        width: '9rem',
        hideBelow: 'md',
        render: (job) => (
          <div className="flex justify-end gap-1">
            {canEdit && job.status === 'failed' ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={busyVersionId === job.version_id}
                data-testid={`processing-job-retry-${job.id}`}
                onClick={(event) => {
                  event.stopPropagation();
                  onRetry(job);
                }}
              >
                {k.history_retry}
              </Button>
            ) : null}
          </div>
        ),
      },
    ],
    [
      busyVersionId,
      canEdit,
      emptyCell,
      k.copy_job_link,
      k.history_attempt,
      k.history_retry,
      k.job_status,
      locale,
      onCopyLink,
      onRetry,
      p.col_actions,
      p.col_attempt,
      p.col_created,
      p.col_document,
      p.col_status,
    ],
  );

  const expandedJob = expandedId ? filtered.find((job) => job.id === expandedId) : undefined;
  return (
    <div data-testid="processing-jobs-list">
      <DataTable
        columns={columns}
        data={filtered}
        rowKey={(job) => job.id}
        emptyMessage={p.no_matches}
        className="border-0"
        rowDomId={(job) => `processing-job-row-${job.id}`}
        rowClassName={(job) =>
          expandedId === job.id ? 'bg-muted/40 hover:bg-muted/40' : undefined
        }
        onRowClick={(job) => setExpandedId((prev) => (prev === job.id ? null : job.id))}
      />
      {expandedJob ? (
        <section
          id={`processing-job-${expandedJob.id}`}
          data-testid={`processing-job-detail-${expandedJob.id}`}
          className="border-t border-border p-4 text-sm"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 space-y-1">
              <p className="font-medium">{expandedJob.document_title || expandedJob.doc_id}</p>
              <p className="text-xs text-muted-foreground">
                {k.job_id}: <span className="font-mono">{expandedJob.id}</span>
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="outline" size="sm" asChild>
                <Link
                  to={sourcesDocumentPath(workspaceId, expandedJob.doc_id)}
                  data-testid={`processing-job-open-sources-${expandedJob.id}`}
                >
                  {p.open_in_sources}
                </Link>
              </Button>
              {graphEnabled && expandedJob.status === 'succeeded' && expandedJob.doc_id ? (
                <Button type="button" variant="outline" size="sm" asChild>
                  <Link to={graphFocusPath(expandedJob.doc_id)}>{k.toast_view_in_graph}</Link>
                </Button>
              ) : null}
              <Button
                type="button"
                variant="outline"
                size="sm"
                data-testid={`processing-job-copy-link-${expandedJob.id}`}
                onClick={() => onCopyLink(expandedJob.id)}
              >
                {k.copy_job_link}
              </Button>
              {expandedJob.status === 'failed' ? (
                <Button type="button" variant="outline" size="sm" asChild>
                  <Link
                    to={workspaceAlertsPath(workspaceId, {
                      episodeKey: processingAlertEpisodeKey(expandedJob.id),
                    })}
                    data-testid={`processing-job-view-alerts-${expandedJob.id}`}
                  >
                    {p.view_related_alerts}
                  </Link>
                </Button>
              ) : null}
              {canEdit && expandedJob.status === 'failed' ? (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={busyVersionId === expandedJob.version_id}
                  data-testid={`processing-job-retry-${expandedJob.id}`}
                  onClick={() => onRetry(expandedJob)}
                >
                  {k.history_retry}
                </Button>
              ) : null}
            </div>
          </div>
          {expandedJob.error_code ? (
            <div className="mt-3 space-y-1 text-xs text-destructive">
              <p data-testid={`processing-job-error-code-${expandedJob.id}`}>
                {messageForApiErrorCode(expandedJob.error_code, locale) ?? expandedJob.error_code}
                <span className="ml-1 font-mono text-[10px] opacity-80">
                  ({expandedJob.error_code})
                </span>
              </p>
              {expandedJob.error_detail?.message ? (
                <p className="text-muted-foreground">{expandedJob.error_detail.message}</p>
              ) : null}
              <p>
                <Link
                  to={sourcesDocumentPath(workspaceId, expandedJob.doc_id)}
                  className="font-medium text-primary hover:underline"
                  data-testid={`processing-job-error-doc-link-${expandedJob.id}`}
                >
                  {p.error_doc_link}
                </Link>
              </p>
            </div>
          ) : null}
          <ProcessingOptionsSnapshot
            className="mt-3"
            options={expandedJob.options ?? {}}
            summaryTestId={`processing-job-options-summary-${expandedJob.id}`}
            jsonTestId={`processing-job-options-json-${expandedJob.id}`}
          />
        </section>
      ) : null}
    </div>
  );
}
