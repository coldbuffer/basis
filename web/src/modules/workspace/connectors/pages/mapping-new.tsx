import { zodResolver } from '@hookform/resolvers/zod';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
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
  defaultConnectorStreamName,
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
import { workspaceOpenApiGET, workspaceOpenApiPOST } from '@/lib/openapi/client.js';

export function ConnectorMappingNewPage() {
  const { id: workspaceId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { t, locale } = useI18n();
  const c = t.connectors.page;
  const { getWorkspace } = useWorkspaceCatalog();

  const prefillService = searchParams.get('service')?.trim() ?? '';
  const prefillConnection = searchParams.get('connection')?.trim() ?? '';

  const [connections, setConnections] = useState<StoredConnection[]>([]);
  const [loadingConnections, setLoadingConnections] = useState(true);
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

  const loadConnections = useCallback(async () => {
    if (!workspaceId) return;
    setLoadingConnections(true);
    try {
      const res = await workspaceOpenApiGET<{ connections: StoredConnection[] }>(
        workspaceId,
        'connectors/connections',
      );
      setConnections(res.connections ?? []);
    } catch (err) {
      toast.error(formatUserFacingApiError(err, locale as Locale));
    } finally {
      setLoadingConnections(false);
    }
  }, [workspaceId, locale]);

  useEffect(() => {
    void loadConnections();
  }, [loadConnections]);

  useEffect(() => {
    if (connections.length === 0) {
      return;
    }
    const fromQuery = prefillService
      ? connections.find(
          (conn) =>
            conn.service === prefillService &&
            (!prefillConnection || conn.service === prefillConnection),
        )
      : undefined;
    const conn = fromQuery ?? connections[0];
    form.reset({
      ...defaultConnectorTableMappingFormValues,
      connectionKey: connectorConnectionSelectKey(conn),
      streamName: defaultConnectorStreamName(conn.service),
    });
  }, [connections, prefillService, prefillConnection, form]);

  if (!workspaceId) {
    return null;
  }

  const resolvedKbId = workspaceId;
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
    if (connections.length === 0) {
      toast.error(c.mappings.no_configured_connections_hint);
      return;
    }
    setSubmitting(true);
    try {
      await workspaceOpenApiPOST(resolvedKbId, 'connectors/table-mappings', {
        body: mappingRequestBodyFromFormValues(values, connections),
      });
      toast.success(c.mappings.created_toast);
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
        { label: c.mappings.new_page_title },
      ]}
      subtitle={c.mappings.new_page_subtitle}
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" asChild>
            <Link to={`${mappingsListPath}?suggest=1`}>{c.mappings.use_suggest_instead}</Link>
          </Button>
          <Button variant="outline" size="sm" asChild>
            <Link to={mappingsListPath}>{c.mappings.cancel_button}</Link>
          </Button>
          <Button
            size="sm"
            type="submit"
            form="connector-table-mapping-form"
            disabled={submitting || connections.length === 0}
            data-testid="submit-table-mapping-btn"
          >
            {submitting ? c.mappings.creating_mapping : c.mappings.save_mapping}
          </Button>
        </div>
      }
    >
      <ConnectorTableMappingForm
        workspaceId={resolvedKbId}
        form={form}
        connections={connections}
        loadingConnections={loadingConnections}
        discovering={discoveringSchema}
        onDiscover={handleDiscoverSchema}
        onSubmit={onSubmit}
      />
    </ConsolePageLayout>
  );
}
