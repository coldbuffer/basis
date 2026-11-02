import { zodResolver } from '@hookform/resolvers/zod';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { toast } from 'sonner';
import { ConnectorTableMappingForm } from '@/modules/workspace/connectors/components/connector-table-mapping-form.js';
import { ConsolePageLayout } from '@/components/app/shared/console/index.js';
import { Button } from '@/components/ui/button.js';
import { useI18n } from '@/i18n/context.js';
import type { Locale } from '@/i18n/locale.js';
import { formatUserFacingApiError } from '@/lib/errors/api-error-message.js';
import {
  connectorConnectionSelectKey,
  connectionIdentityFromOptionKey,
  workspaceConnectionOptionKey,
  workspaceConnectorsMappingsTabPath,
  type StoredConnection,
} from '@/modules/workspace/connectors/lib/connector-connections.js';
import {
  columnSpecFromMappings,
  createConnectorTableMappingFormSchema,
  defaultConnectorTableMappingFormValues,
  mappingRequestBodyFromFormValues,
  type ConnectorTableMappingFormValues,
} from '@/modules/workspace/connectors/lib/connector-mapping-form.js';
import { useWorkspaceCatalog } from '@/lib/workspace/context.js';
import { workspaceConnectorPanelPath, workspacePath } from '@/lib/nav/nav-config.js';
import { fieldMapFromStreamParams } from '@/modules/workspace/connectors/lib/connector-stream-params.js';
import { workspaceOpenApiGET, workspaceOpenApiPUT } from '@/lib/openapi/client.js';

type MappingDto = {
  id: string;
  provider: string;
    stream_name: string;
  external_table: string;
  stream_params: Record<string, unknown>;
  primary_key_column: string;
  cursor_column?: string | null;
  label_column: string;
  target_class_uri: string;
  column_mappings: Array<{ column: string; writable?: boolean }>;
  sync_mode: 'full_refresh' | 'incremental';
  track_deletes: boolean;
  sync_direction: 'inbound' | 'bidirectional';
  writeback_mode: 'disabled' | 'review' | 'auto';
  poll_interval_minutes?: number;
};

export function ConnectorMappingEditPage() {
  const { id: workspaceId, mappingId } = useParams();
  const navigate = useNavigate();
  const { t, locale } = useI18n();
  const c = t.connectors.page;
  const { getWorkspace } = useWorkspaceCatalog();

  const [connections, setConnections] = useState<StoredConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [discoveringSchema, setDiscoveringSchema] = useState(false);

  const schema = useMemo(
    () =>
      createConnectorTableMappingFormSchema({
        invalidJson: c.mappings.validation_invalid_json,
        invalidJsonObject: c.mappings.validation_invalid_json_object,
      }),
    [c.mappings.validation_invalid_json, c.mappings.validation_invalid_json_object],
  );

  const form = useForm<ConnectorTableMappingFormValues>({
    resolver: zodResolver(schema),
    defaultValues: defaultConnectorTableMappingFormValues,
  });

  const load = useCallback(async () => {
    if (!workspaceId || !mappingId) return;
    setLoading(true);
    try {
      const [connRes, mapRes] = await Promise.all([
        workspaceOpenApiGET<{ connections: StoredConnection[] }>(workspaceId, 'connectors/connections'),
        workspaceOpenApiGET<{ mapping: MappingDto }>(workspaceId, `connectors/table-mappings/${mappingId}`),
      ]);
      const loadedConnections = connRes.connections ?? [];
      setConnections(loadedConnections);
      const m = mapRes.mapping;
      const matchedConnection = loadedConnections.find(
        (conn) => conn.service === m.provider,
      );
      form.reset({
        connectionKey: matchedConnection
          ? connectorConnectionSelectKey(matchedConnection)
          : workspaceConnectionOptionKey({
              service: m.provider,
                          }),
        streamName: m.stream_name,
        externalTable: m.external_table,
        streamParamsAdvanced: false,
        streamParamFields: fieldMapFromStreamParams(m.stream_params),
        streamParamsJson: JSON.stringify(m.stream_params ?? {}, null, 2),
        primaryKeyColumn: m.primary_key_column,
        cursorColumn: m.cursor_column ?? '',
        labelColumn: m.label_column,
        targetClassUri: m.target_class_uri,
        columnsSpec: columnSpecFromMappings(m.column_mappings),
        syncDirection: m.sync_direction,
        writebackMode: m.writeback_mode,
        syncMode: m.sync_mode,
        trackDeletes: m.track_deletes,
        pollIntervalMinutes: m.poll_interval_minutes ?? 0,
      });
    } catch (err) {
      toast.error(formatUserFacingApiError(err, locale as Locale));
      navigate(workspaceConnectorsMappingsTabPath(workspaceId));
    } finally {
      setLoading(false);
    }
  }, [workspaceId, mappingId, form, locale, navigate]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!workspaceId || !mappingId) {
    return null;
  }

  const resolvedKbId = workspaceId;
  const resolvedMappingId = mappingId;
  const mappingsListPath = workspaceConnectorsMappingsTabPath(resolvedKbId);

  async function handleDiscoverSchema() {
    const values = form.getValues();
    const { service } = connectionIdentityFromOptionKey(
      values.connectionKey,
      connections,
    );
    setDiscoveringSchema(true);
    try {
      const info = await workspaceOpenApiGET<{
        primary_key: string[];
        cursor_field?: string | null;
        fields: Array<{ name: string; writable?: boolean }>;
      }>(
        resolvedKbId,
        `connectors/connections/${service}/discover`,
        {
          params: {
            query: {
              stream_name: values.streamName.trim() || undefined,
              external_table: values.externalTable.trim() || undefined,
            },
          },
        },
      );
      if (info.primary_key?.[0]) {
        form.setValue('primaryKeyColumn', info.primary_key[0], { shouldValidate: true });
      }
      if (info.cursor_field) {
        form.setValue('cursorColumn', info.cursor_field, { shouldValidate: true });
      }
      const pkSet = new Set(info.primary_key ?? []);
      const attrFields = (info.fields ?? []).filter((f) => !pkSet.has(f.name));
      if (attrFields.length > 0) {
        const candidateLabel =
          attrFields.find((f) => /name|title|label/i.test(f.name)) ?? attrFields[0];
        if (candidateLabel) {
          form.setValue('labelColumn', candidateLabel.name, { shouldValidate: true });
        }
        form.setValue(
          'columnsSpec',
          attrFields
            .filter((f) => f.name !== candidateLabel?.name)
            .map((f) => `${f.name}:${f.writable !== false ? 'writable' : 'readonly'}`)
            .join(','),
          { shouldValidate: true },
        );
      }
    } catch (err) {
      toast.error(formatUserFacingApiError(err, locale as Locale));
    } finally {
      setDiscoveringSchema(false);
    }
  }

  async function onSubmit(values: ConnectorTableMappingFormValues) {
    setSubmitting(true);
    try {
      await workspaceOpenApiPUT(resolvedKbId, `connectors/table-mappings/${resolvedMappingId}`, {
        body: mappingRequestBodyFromFormValues(values, connections),
      });
      toast.success(c.mappings.updated_toast);
      navigate(mappingsListPath);
    } catch (err) {
      toast.error(formatUserFacingApiError(err, locale as Locale));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <ConsolePageLayout
      crumbs={[
        { label: t.core.workspace_nav.platform.workspaces, to: '/workspaces' },
        { label: getWorkspace(workspaceId)?.name ?? workspaceId, to: workspacePath(workspaceId, 'graph') },
        {
          label: t.connectors.menu.connector_stream_mappings,
          to: workspaceConnectorPanelPath(workspaceId, 'mappings'),
        },
        { label: c.mappings.edit_page_title },
      ]}
      subtitle={c.mappings.edit_page_subtitle}
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" asChild>
            <Link to={mappingsListPath}>{c.mappings.cancel_button}</Link>
          </Button>
          <Button
            size="sm"
            type="submit"
            form="connector-table-mapping-form"
            disabled={submitting || loading}
            data-testid="submit-table-mapping-btn"
          >
            {submitting ? c.mappings.saving_mapping : c.mappings.save_changes}
          </Button>
        </div>
      }
    >
      {loading ? (
        <p className="text-sm text-muted-foreground">{c.mappings.loading_mapping}</p>
      ) : (
        <ConnectorTableMappingForm
          workspaceId={resolvedKbId}
          form={form}
          connections={connections}
          loadingConnections={loading}
          discovering={discoveringSchema}
          onDiscover={handleDiscoverSchema}
          onSubmit={onSubmit}
        />
      )}
    </ConsolePageLayout>
  );
}
