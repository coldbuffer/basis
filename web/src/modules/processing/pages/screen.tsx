import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';
import {
  DataPanel,
  DataPanelBody,
  DataPanelToolbar,
  EmptyState,
  ToolbarSearch,
} from '@/components/app/shared/console/index.js';
import { ConsolePageLayout } from '@/components/app/shared/console/index.js';
import { Button } from '@/components/ui/button.js';
import { Spinner } from '@/components/ui/spinner.js';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs.js';
import {
  ProcessingJobsList,
  type ProcessingJobFilter,
} from '../components/processing-jobs-list.js';
import { useI18n } from '@/i18n/context.js';
import { fmt, formatLocaleNumber } from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import { formatUserFacingApiError } from '@/lib/errors/api-error-message.js';
import { useWorkspaceWsClient } from '@/lib/workspace/ws-context.js';
import { useWorkspaceCatalog } from '@/lib/workspace/context.js';
import { useWorkspaceCapabilities } from '@/lib/workspace/capabilities.js';
import {
  type ProcessingJob,
  jobIsActive,
  sortProcessingJobs,
} from '@/modules/processing/lib/processing-job.js';
import { workspacePath } from '@/lib/nav/nav-config.js';
import { processingPath } from '@/modules/processing/lib/processing-url-state.js';

export function ProcessingScreen({
  workspaceId,
  jobFocusId,
  initialFilter = 'all',
}: {
  workspaceId: string;
  jobFocusId?: string;
  initialFilter?: ProcessingJobFilter;
}) {
  const [, setSearchParams] = useSearchParams();
  const client = useWorkspaceWsClient();
  const { t, locale } = useI18n();
  const { getWorkspace } = useWorkspaceCatalog();
  const { caps } = useWorkspaceCapabilities();
  const jobStatusRef = useRef<Record<string, string>>({});

  const [jobs, setJobs] = useState<ProcessingJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [busyVersionId, setBusyVersionId] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<ProcessingJobFilter>(initialFilter);

  useEffect(() => {
    setFilter(initialFilter);
  }, [initialFilter]);

  const onFilterChange = useCallback(
    (value: ProcessingJobFilter) => {
      setFilter(value);
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (value === 'all') {
            next.delete('filter');
          } else {
            next.set('filter', value);
          }
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  const k = t.library.sources;
  const p = t.processing.jobs;
  const apiErrorMessage = useCallback(
    (err: unknown) => formatUserFacingApiError(err, locale as Locale),
    [locale],
  );
  const canEdit = caps?.graph_write !== false;
  const graphEnabled = caps?.graph === true;
  const kbName = getWorkspace(workspaceId)?.name ?? workspaceId;

  const sortedJobs = useMemo(() => sortProcessingJobs(jobs), [jobs]);

  const activeJobCount = useMemo(
    () => jobs.filter((job) => jobIsActive(job.status)).length,
    [jobs],
  );
  const failedJobCount = useMemo(
    () => jobs.filter((job) => job.status === 'failed').length,
    [jobs],
  );

  const refresh = useCallback(
    async (silent = false) => {
      if (!silent) setRefreshing(true);
      try {
        const taskData = await client.processing.list();
        setJobs(taskData.jobs as ProcessingJob[]);
        window.dispatchEvent(new CustomEvent('workspace-processing-changed'));
      } catch (err) {
        toast.error(apiErrorMessage(err));
      } finally {
        if (!silent) setRefreshing(false);
      }
    },
    [apiErrorMessage, client],
  );

  useEffect(() => {
    setLoading(true);
    void refresh(true)
      .catch(() => undefined)
      .finally(() => setLoading(false));
  }, [refresh]);

  useEffect(() => {
    if (!jobs.some((job) => jobIsActive(job.status))) return;
    const timer = window.setInterval(() => void refresh(true), 2000);
    return () => window.clearInterval(timer);
  }, [jobs, refresh]);

  useEffect(() => {
    if (!graphEnabled) return;
    for (const job of jobs) {
      const prev = jobStatusRef.current[job.id];
      jobStatusRef.current[job.id] = job.status;
      if (prev && prev !== 'succeeded' && job.status === 'succeeded' && job.doc_id) {
        toast.success(k.toast_processing_complete, {
          description: job.document_title || job.doc_id,
        });
      }
    }
  }, [graphEnabled, jobs, k.toast_processing_complete]);

  async function retry(job: ProcessingJob) {
    setBusyVersionId(job.version_id);
    try {
      await client.processing.retry(job.id);
      toast.success(k.toast_retry_queued);
      await refresh(true);
    } catch (err) {
      toast.error(apiErrorMessage(err));
    } finally {
      setBusyVersionId(null);
    }
  }

  async function retryAllFailed() {
    const failed = jobs.filter((job) => job.status === 'failed');
    if (failed.length === 0) return;
    setBusyVersionId('bulk');
    try {
      await Promise.allSettled(failed.map((job) => client.processing.retry(job.id)));
      toast.success(p.retry_all_queued);
      await refresh(true);
    } catch (err) {
      toast.error(apiErrorMessage(err));
    } finally {
      setBusyVersionId(null);
    }
  }

  async function copyJobDeepLink(jobId: string) {
    const url = `${window.location.origin}${workspacePath(workspaceId, 'processing')}?job=${encodeURIComponent(jobId)}`;
    try {
      await navigator.clipboard.writeText(url);
      toast.success(t.core.common.copySuccess);
    } catch {
      toast.error(t.core.common.copy);
    }
  }

  const showEmpty = !loading && jobs.length === 0;
  const showFilterTabs = !loading && (jobs.length > 0 || filter !== 'all');

  return (
    <div
      className="basis-processing-view w-full"
      data-workspace-id={workspaceId}
      data-testid="workspace-processing-view"
    >
      <ConsolePageLayout
        crumbs={[
          { label: t.core.workspace_nav.platform.workspaces, to: '/workspaces' },
          { label: kbName, to: workspacePath(workspaceId, 'graph') },
          { label: t.processing.menu.processing },
        ]}
        subtitle={t.processing.page.subtitle}
        className="gap-6 [&>:last-child]:min-h-0 [&>:last-child]:flex-none"
      >
        <DataPanel>
          <DataPanelToolbar
            className="flex-col items-stretch gap-3 sm:flex-row sm:items-center"
            search={
              <ToolbarSearch
                className="min-w-0 w-full max-w-md flex-1"
                placeholder={p.search_placeholder}
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                disabled={showEmpty}
              />
            }
            actions={
              <div className="flex flex-wrap items-center gap-2">
                {activeJobCount > 0 ? (
                  <span
                    className="inline-flex items-center gap-1.5 rounded-md bg-primary/15 px-2 py-1 text-xs font-medium text-primary"
                    data-testid="processing-active-jobs-badge"
                  >
                    <Spinner className="size-3" />
                    {formatLocaleNumber(locale as Locale, activeJobCount)}
                  </span>
                ) : failedJobCount > 0 ? (
                  <Link
                    to={processingPath(workspaceId, { filter: 'failed' })}
                    className="inline-flex min-w-[1.25rem] items-center justify-center rounded-md bg-destructive/15 px-2 py-1 text-xs font-medium tabular-nums text-destructive underline-offset-2 hover:underline"
                    data-testid="processing-failed-jobs-badge"
                  >
                    {formatLocaleNumber(locale as Locale, failedJobCount)}
                  </Link>
                ) : null}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={loading || refreshing}
                  onClick={() => void refresh()}
                >
                  <PublicIcon
                    name="arrow-refresh-01"
                    className={`mr-1.5 size-3.5 ${refreshing ? 'animate-spin' : ''}`}
                  />
                  {p.refresh}
                </Button>
                {canEdit && failedJobCount > 0 ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={busyVersionId !== null}
                    data-testid="processing-retry-all-failed"
                    onClick={() => void retryAllFailed()}
                  >
                    {p.retry_all_failed}
                  </Button>
                ) : null}
                <Button type="button" variant="outline" size="sm" asChild>
                  <Link to={workspacePath(workspaceId, 'sources')}>{t.library.menu.sources}</Link>
                </Button>
                {failedJobCount > 0 ? (
                  <Button type="button" variant="outline" size="sm" asChild>
                    <Link to={workspacePath(workspaceId, 'alerts')} data-testid="processing-view-alerts">
                      {p.view_alerts}
                    </Link>
                  </Button>
                ) : null}
                <Button type="button" variant="outline" size="sm" asChild>
                  <Link
                    to={`${workspacePath(workspaceId, 'integration')}?tab=openapi`}
                    data-testid="processing-jobs-openapi-link"
                  >
                    {p.jobs_api_link}
                  </Link>
                </Button>
              </div>
            }
          />
          <DataPanelBody padded={false} className="mt-2">
            {showFilterTabs ? (
              <div className="border-b border-border px-3 py-2 sm:px-4">
                <Tabs
                  value={filter}
                  onValueChange={(value) => onFilterChange(value as ProcessingJobFilter)}
                >
                  <TabsList className="h-8">
                    <TabsTrigger value="all" className="px-3 text-xs">
                      {p.filter_all}
                    </TabsTrigger>
                    <TabsTrigger value="active" className="px-3 text-xs">
                      {p.filter_active}
                      {activeJobCount > 0 ? (
                        <span className="ml-1 tabular-nums text-muted-foreground">
                          ({formatLocaleNumber(locale as Locale, activeJobCount)})
                        </span>
                      ) : null}
                    </TabsTrigger>
                    <TabsTrigger value="failed" className="px-3 text-xs">
                      {p.filter_failed}
                      {failedJobCount > 0 ? (
                        <span className="ml-1 tabular-nums text-muted-foreground">
                          ({formatLocaleNumber(locale as Locale, failedJobCount)})
                        </span>
                      ) : null}
                    </TabsTrigger>
                    <TabsTrigger value="succeeded" className="px-3 text-xs">
                      {p.filter_succeeded}
                    </TabsTrigger>
                  </TabsList>
                </Tabs>
              </div>
            ) : null}
            {loading && jobs.length === 0 ? (
              <div className="flex justify-center py-16">
                <Spinner className="size-6" />
              </div>
            ) : showEmpty && filter === 'all' ? (
              <div className="p-4">
                <EmptyState
                  title={k.no_jobs}
                  description={k.empty_description}
                  action={
                    <Button type="button" size="sm" asChild>
                      <Link to={workspacePath(workspaceId, 'sources')}>{k.add_document}</Link>
                    </Button>
                  }
                />
              </div>
            ) : (
              <ProcessingJobsList
                workspaceId={workspaceId}
                jobs={sortedJobs}
                jobFocusId={jobFocusId}
                canEdit={canEdit}
                busyVersionId={busyVersionId}
                graphEnabled={graphEnabled}
                search={search}
                filter={filter}
                onRetry={(job) => void retry(job)}
                onCopyLink={(jobId) => void copyJobDeepLink(jobId)}
              />
            )}
          </DataPanelBody>
        </DataPanel>
      </ConsolePageLayout>
    </div>
  );
}
