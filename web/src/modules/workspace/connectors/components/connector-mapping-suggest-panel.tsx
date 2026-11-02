import { useCallback, useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';
import { Badge } from '@/components/ui/badge.js';
import { Button } from '@/components/ui/button.js';
import { Checkbox } from '@/components/ui/checkbox.js';
import { DialogFooter } from '@/components/ui/dialog.js';
import { Label } from '@/components/ui/label.js';
import { Textarea } from '@/components/ui/textarea.js';
import { useI18n } from '@/i18n/context.js';
import { fmt } from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import { formatUserFacingApiError } from '@/lib/errors/api-error-message.js';
import { workspaceOpenApiPOST } from '@/lib/openapi/client.js';
import type { StoredConnection } from '@/modules/workspace/connectors/lib/connector-connections.js';
import { buildSqlSuggestTargets } from '@/modules/workspace/connectors/lib/sql-suggest-targets.js';
import type { ConnectorMappingDraft } from '@/modules/workspace/connectors/lib/connector-mapping-draft.js';

type SuggestDraftRow = {
  key: string;
  entity_group_label: string;
  confidence: string;
  source_label: string;
  draft: ConnectorMappingDraft;
};

type SuggestResponse = {
  groups: Array<{
    id: string;
    label: string;
    drafts: Array<{
      source_label: string;
      confidence: string;
      entity_group_label: string;
      draft: ConnectorMappingDraft;
    }>;
  }>;
  skipped: Array<{ reason: string }>;
};

function draftKey(draft: ConnectorMappingDraft): string {
  return `${draft.provider}:${draft.stream_name}:${draft.external_table}`;
}

const SQL_SERVICES = new Set(['postgres', 'mysql']);

type Props = {
  workspaceId: string;
  selectedConnection: StoredConnection | null;
  active?: boolean;
  onClose: () => void;
  onApplied?: (createdCount: number) => void;
};

export function ConnectorMappingSuggestPanel({
  workspaceId,
  selectedConnection,
  active = true,
  onClose,
  onApplied,
}: Props) {
  const { t, locale } = useI18n();
  const s = t.connectors.page.suggest;
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [rows, setRows] = useState<SuggestDraftRow[]>([]);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [skippedCount, setSkippedCount] = useState(0);
  const [sqlTableInput, setSqlTableInput] = useState('');
  const [hasGenerated, setHasGenerated] = useState(false);

  useEffect(() => {
    if (!active) {
      return;
    }
    setRows([]);
    setSelected({});
    setSkippedCount(0);
    setHasGenerated(false);
    setSqlTableInput('');
  }, [active, selectedConnection?.service, selectedConnection?.service]);

  const fetchSuggestions = useCallback(async () => {
    if (!selectedConnection) {
      return;
    }
    setLoading(true);
    try {
      const scoped = [selectedConnection];
      const sqlTables = buildSqlSuggestTargets(scoped, sqlTableInput);
      const body: Record<string, unknown> = {
        connections: [
          {
            provider: selectedConnection.service,
                      },
        ],
      };
      if (sqlTables.length) {
        body.sql_tables = sqlTables.map((row) => ({
          provider: row.provider,
                    stream_name: row.stream_name ?? 'table_records',
          external_table: row.external_table,
        }));
      }
      const res = await workspaceOpenApiPOST<SuggestResponse>(
        workspaceId,
        'connectors/table-mappings/suggest',
        { body },
      );
      const flat: SuggestDraftRow[] = [];
      for (const group of res.groups ?? []) {
        for (const item of group.drafts ?? []) {
          const key = draftKey(item.draft);
          flat.push({
            key,
            entity_group_label: item.entity_group_label,
            confidence: item.confidence,
            source_label: item.source_label,
            draft: item.draft,
          });
        }
      }
      setRows(flat);
      setSkippedCount(res.skipped?.length ?? 0);
      const initial: Record<string, boolean> = {};
      for (const row of flat) {
        initial[row.key] = true;
      }
      setSelected(initial);
      setHasGenerated(true);
    } catch (err) {
      toast.error(formatUserFacingApiError(err, locale as Locale));
    } finally {
      setLoading(false);
    }
  }, [workspaceId, selectedConnection, sqlTableInput, locale]);

  const selectedDrafts = useMemo(
    () => rows.filter((r) => selected[r.key]).map((r) => r.draft),
    [rows, selected],
  );

  const applySelected = async () => {
    if (selectedDrafts.length === 0) {
      return;
    }
    setApplying(true);
    try {
      await workspaceOpenApiPOST(workspaceId, 'connectors/table-mappings/batch-create', {
        body: { mappings: selectedDrafts, run_sync: true },
      });
      toast.success(fmt(s.applied_toast, { count: selectedDrafts.length }));
      onClose();
      onApplied?.(selectedDrafts.length);
    } catch (err) {
      toast.error(formatUserFacingApiError(err, locale as Locale));
    } finally {
      setApplying(false);
    }
  };

  const showSqlSection = selectedConnection
    ? SQL_SERVICES.has(selectedConnection.service)
    : false;

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">{s.panel_description}</p>
      {showSqlSection ? (
        <div className="space-y-2 border-b border-border pb-4">
          <Label htmlFor="connector-suggest-sql-tables">{s.sql_tables_label}</Label>
          <Textarea
            id="connector-suggest-sql-tables"
            className="min-h-[4.5rem] font-mono text-xs"
            value={sqlTableInput}
            onChange={(e) => setSqlTableInput(e.target.value)}
            placeholder={s.sql_tables_placeholder}
            spellCheck={false}
          />
          <p className="text-xs text-muted-foreground">{s.sql_tables_hint}</p>
        </div>
      ) : null}
      <Button
        type="button"
        size="sm"
        disabled={loading || !selectedConnection}
        onClick={() => void fetchSuggestions()}
        data-testid="suggest-generate-btn"
      >
        {loading ? s.loading : s.generate_button}
      </Button>
      {!hasGenerated && !loading ? (
        <p className="text-sm text-muted-foreground">{s.prompt_generate}</p>
      ) : null}
      {loading ? (
        <p className="text-sm text-muted-foreground">{s.loading}</p>
      ) : hasGenerated && rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">{s.empty}</p>
      ) : rows.length > 0 ? (
        <div className="space-y-2">
          {rows.map((row) => (
            <label
              key={row.key}
              className="flex cursor-pointer items-start gap-3 rounded-md border border-border p-3"
            >
              <Checkbox
                checked={selected[row.key] ?? false}
                onCheckedChange={(v) =>
                  setSelected((prev) => ({ ...prev, [row.key]: v === true }))
                }
              />
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-sm">{row.draft.external_table}</span>
                  <span className="text-muted-foreground">→</span>
                  <Badge variant="outline" className="font-mono text-xs">
                    {row.draft.target_class_uri}
                  </Badge>
                  <Badge variant="secondary" className="text-[10px]">
                    {row.entity_group_label}
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground">{row.source_label}</p>
              </div>
            </label>
          ))}
        </div>
      ) : null}
      {skippedCount > 0 ? (
        <p className="text-xs text-muted-foreground">
          {fmt(s.skipped_summary, { count: skippedCount })}
        </p>
      ) : null}
      <DialogFooter className="gap-2 px-0 sm:gap-0">
        <Button variant="outline" onClick={onClose}>
          {s.cancel_button}
        </Button>
        <Button
          disabled={loading || applying || selectedDrafts.length === 0}
          onClick={() => void applySelected()}
        >
          <PublicIcon name="sync" size={14} className="mr-1" />
          {applying ? s.applying : fmt(s.apply_button, { count: selectedDrafts.length })}
        </Button>
      </DialogFooter>
    </div>
  );
}
