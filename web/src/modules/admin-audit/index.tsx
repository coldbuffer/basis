import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { GraphAuditEventLinks } from '@/components/app/shared/workspace/graph-audit-event-links.js';
import {
  DataPanel,
  DataPanelBody,
  DataPanelTableFooter,
  DataPanelToolbar,
  EmptyState,
  ToolbarSearch,
} from '@/components/app/shared/console/index.js';
import { DataTable, type DataTableColumn } from '@/components/app/shared/console/DataTable.js';
import { ConsolePageLayout } from '@/components/app/shared/console/index.js';
import { Button } from '@/components/ui/button.js';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select.js';
import { Spinner } from '@/components/ui/spinner.js';
import { useI18n } from '@/i18n/context.js';
import { fmt, formatLocaleDateTime, formatLocaleNumber, pickCountForm } from '@/i18n/format.js';
import type { LocaleMessages } from '@/i18n/en.js';
import { openApiGET } from '@/lib/openapi/client.js';
import { formatUserFacingApiError } from '@/lib/errors/api-error-message.js';
import type { Locale } from '@/i18n/locale.js';
import {
  formatBasisAuditMemberRole,
  formatBasisAuditModelKind,
} from '@/modules/admin-audit/lib/basis-audit-detail.js';
import {
  formatGraphAuditAction,
  formatGraphAuditDetail,
  workspaceIdFromPlatformAuditEvent,
  type GraphAuditEvent,
} from '@/modules/graph/lib/graph-audit.js';
import { decisionIdFromDetail } from '@/modules/review/lib/review-url-state.js';
import { usePlatformAdminCrumbs } from '@/lib/admin/use-platform-admin-crumbs.js';

type AuditDetail = Record<string, unknown>;

type Event = {
  id: number;
  action: string;
  actor_id: string | null;
  target_type: string;
  target_id: string | null;
  detail: AuditDetail;
  created_at: string;
};

const ACTION_PRESET_VALUES = ['all', 'workspace.graph.', 'workspace.', 'settings.'] as const;

function actionPresetLabel(
  value: (typeof ACTION_PRESET_VALUES)[number],
  p: {
    action_all: string;
    action_graph: string;
    action_workspace: string;
    action_settings: string;
  },
): string {
  if (value === 'all') return p.action_all;
  if (value === 'workspace.graph.') return p.action_graph;
  if (value === 'workspace.') return p.action_workspace;
  return p.action_settings;
}

type BasisAuditCopy = LocaleMessages['admin_audit']['page'];

function formatDetailSummary(
  locale: Locale,
  p: BasisAuditCopy,
  detail: AuditDetail,
  emptyCell: string,
): string {
  const parts: string[] = [];
  if (typeof detail.workspace_id === 'string') {
    parts.push(fmt(p.detail_workspace, { workspaceId: detail.workspace_id }));
  }
  if (detail.projection_revision != null) {
    parts.push(
      fmt(p.detail_rev, {
        revision: formatLocaleNumber(locale, Number(detail.projection_revision)),
      }),
    );
  }
  if (typeof detail.review_item_id === 'string') {
    parts.push(fmt(p.detail_review, { reviewId: detail.review_item_id }));
  }
  const decisionId = decisionIdFromDetail(detail);
  if (decisionId) {
    parts.push(fmt(p.detail_decision, { decisionId }));
  }
  if (typeof detail.email === 'string') {
    parts.push(fmt(p.detail_email, { email: detail.email }));
  }
  if (typeof detail.name === 'string') {
    parts.push(fmt(p.detail_workspace_name, { name: detail.name }));
  }
  if (typeof detail.user_id === 'string') {
    parts.push(fmt(p.detail_user, { userId: detail.user_id }));
  }
  if (typeof detail.role === 'string') {
    parts.push(fmt(p.detail_role, { role: formatBasisAuditMemberRole(locale, detail.role) }));
  }
  if (typeof detail.reason === 'string') {
    parts.push(fmt(p.detail_reason, { reason: detail.reason }));
  }
  if (Array.isArray(detail.keys) && detail.keys.every((k) => typeof k === 'string')) {
    parts.push(fmt(p.detail_keys, { keys: detail.keys.join(', ') }));
  }
  if (typeof detail.kind === 'string') {
    parts.push(fmt(p.detail_kind, { kind: formatBasisAuditModelKind(locale, detail.kind) }));
  }
  if (parts.length > 0) return parts.join(' · ');
  const keys = Object.keys(detail);
  if (keys.length === 0) return emptyCell;
  return keys.length <= 3
    ? JSON.stringify(detail)
    : `${JSON.stringify(Object.fromEntries(keys.slice(0, 2).map((k) => [k, detail[k]])))}…`;
}

function formatAuditEventDetail(
  event: Event,
  locale: Locale,
  p: BasisAuditCopy,
  emptyCell: string,
): string {
  const graphEvent: GraphAuditEvent = {
    id: event.id,
    action: event.action,
    actor_id: event.actor_id,
    created_at: event.created_at,
    detail: event.detail,
  };
  const graphLine = formatGraphAuditDetail(graphEvent, locale);
  if (graphLine && graphLine !== emptyCell) {
    return graphLine;
  }
  return formatDetailSummary(locale, p, event.detail ?? {}, emptyCell);
}

export function AuditPage() {
  const { locale, t } = useI18n();
  const p = t.admin_audit.page;
  const crumbs = usePlatformAdminCrumbs(t.core.workspace_nav.platform.audit);
  const emptyCell = t.core.common.emptyCell;
  const [searchParams, setSearchParams] = useSearchParams();
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const actionPreset = searchParams.get('action_prefix') ?? 'all';
  const kbFilter = searchParams.get('workspace_id') ?? '';
  const [workspaceDraft, setWorkspaceDraft] = useState(kbFilter);

  useEffect(() => {
    setWorkspaceDraft(kbFilter);
  }, [kbFilter]);

  function applyWorkspaceFilter() {
    setFilter('workspace_id', workspaceDraft.trim());
  }

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const query: Record<string, string> = { limit: '100' };
    if (kbFilter.trim()) query.workspace_id = kbFilter.trim();
    if (actionPreset && actionPreset !== 'all') {
      query.action_prefix = actionPreset;
    }
    try {
      const body = await openApiGET<{ events: Event[] }>('/api/v1/audit', { params: { query } });
      setEvents(body.events);
    } catch (err) {
      setError(formatUserFacingApiError(err, locale as Locale));
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }, [actionPreset, kbFilter, locale]);

  useEffect(() => {
    void load();
  }, [load]);

  function setFilter(key: 'action_prefix' | 'workspace_id', value: string) {
    const next = new URLSearchParams(searchParams);
    if (!value || value === 'all') next.delete(key);
    else next.set(key, value);
    setSearchParams(next, { replace: true });
  }

  const columns = useMemo<DataTableColumn<Event>[]>(
    () => [
      {
        key: 'time',
        header: p.col_time,
        render: (e) => formatLocaleDateTime(locale as Locale, e.created_at),
      },
      {
        key: 'action',
        header: p.col_action,
        render: (e) => (
          <span className="font-mono text-xs">
            {formatGraphAuditAction(e.action, locale as Locale)}
          </span>
        ),
      },
      {
        key: 'detail',
        header: p.col_summary,
        hideBelow: 'md',
        render: (e) => (
          <span className="line-clamp-2 text-xs text-muted-foreground">
            {formatAuditEventDetail(e, locale as Locale, p, emptyCell)}
          </span>
        ),
      },
      {
        key: 'links',
        header: p.col_links,
        hideBelow: 'lg',
        render: (e) => {
          const workspaceId = workspaceIdFromPlatformAuditEvent(e);
          if (!workspaceId) return emptyCell;
          return (
            <GraphAuditEventLinks
              workspaceId={workspaceId}
              detail={e.detail}
              testIdPrefix={`platform-audit-${e.id}`}
            />
          );
        },
      },
      { key: 'actor', header: p.col_actor, render: (e) => e.actor_id ?? emptyCell },
    ],
    [emptyCell, locale, p],
  );

  const countLabel = fmt(
    pickCountForm(locale, events.length, p.count_one, p.count),
    { count: formatLocaleNumber(locale, events.length) },
  );

  return (
    <ConsolePageLayout crumbs={crumbs}>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      <DataPanel>
        <DataPanelToolbar
          search={
            <ToolbarSearch
              className="w-full min-w-[12rem] max-w-md sm:w-72"
              placeholder={p.workspace_filter_placeholder}
              value={workspaceDraft}
              onChange={(event) => setWorkspaceDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault();
                  applyWorkspaceFilter();
                }
              }}
            />
          }
          actions={
            <>
              <Select
                value={actionPreset}
                onValueChange={(value) => setFilter('action_prefix', value)}
              >
                <SelectTrigger className="w-[11rem]" size="sm">
                  <SelectValue placeholder={p.action_type_placeholder} />
                </SelectTrigger>
                <SelectContent>
                  {ACTION_PRESET_VALUES.map((value) => (
                    <SelectItem key={value} value={value}>
                      {actionPresetLabel(value, p)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button type="button" variant="outline" size="sm" onClick={applyWorkspaceFilter}>
                {p.apply}
              </Button>
              <Button type="button" variant="outline" size="sm" onClick={() => void load()}>
                {p.refresh}
              </Button>
            </>
          }
        />
        <DataPanelBody padded={false}>
          {loading ? (
            <div className="flex justify-center py-16">
              <Spinner className="size-6" />
            </div>
          ) : events.length === 0 ? (
            <EmptyState title={p.empty_title} description={p.empty_description} />
          ) : (
            <>
              <DataTable columns={columns} data={events} rowKey={(e) => e.id} className="border-0" />
              <DataPanelTableFooter
                countLabel={countLabel}
                page={1}
                totalPages={1}
                onPageChange={() => {}}
              />
            </>
          )}
        </DataPanelBody>
      </DataPanel>
    </ConsolePageLayout>
  );
}
