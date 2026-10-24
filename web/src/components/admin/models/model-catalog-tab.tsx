import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';
import {
  ConfiguredProvidersList,
  type ConfiguredProviderRow,
} from '@/components/admin/models/configured-providers-list.js';
import { ModelCredentialsForm } from '@/components/admin/models/model-credentials-form.js';
import type { ModelKind } from '@/components/admin/models/model-endpoint-panel.js';
import { DataPanel, DataPanelBody } from '@/components/app/shared/console/DataPanel.js';
import { useI18n } from '@/i18n/context.js';
import { openApiDELETE, openApiGET } from '@/lib/openapi/client.js';
import { useApiErrorMessage } from '@/lib/errors/use-api-error-message.js';

export type { ConfiguredModelRow as ConfiguredModel } from '@/components/admin/models/group-configured-models.js';

type Props = {
  kind: ModelKind;
};

/** Platform model credentials per provider endpoint. Model IDs are chosen on feature screens. */
export function ModelCatalogTab({ kind }: Props) {
  const { t } = useI18n();
  const m = t.admin_models.page;
  const apiError = useApiErrorMessage();
  const [endpoints, setEndpoints] = useState<ConfiguredProviderRow[]>([]);
  const [editing, setEditing] = useState<ConfiguredProviderRow | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const body = await openApiGET<{ models: ConfiguredProviderRow[] }>('/api/v1/models', {
        params: { query: { kind } },
      });
      const rows = body.models.map((row) => ({
        id: row.id,
        provider: row.provider,
        api_base: row.api_base,
        configured: row.configured,
      }));
      setEndpoints(rows);
      return rows;
    } catch (err) {
      toast.error(apiError(err));
      setEndpoints([]);
      return [];
    } finally {
      setLoading(false);
    }
  }, [kind, apiError]);

  useEffect(() => {
    void load();
  }, [load]);

  async function removeEndpoint(row: ConfiguredProviderRow) {
    setBusyId(row.id);
    try {
      await openApiDELETE('/api/v1/models/{model_id}', {
        params: { path: { model_id: row.id } },
      });
      toast.success(m.removed_provider_toast);
      if (editing?.id === row.id) {
        setEditing(null);
        setSelectedId(null);
      }
      await load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setBusyId(null);
    }
  }

  function selectEndpoint(row: ConfiguredProviderRow) {
    setEditing(row);
    setSelectedId(row.id);
  }

  function startAddProvider() {
    setEditing(null);
    setSelectedId(null);
  }

  const providerLabels = m.providers as Record<string, string>;

  return (
    <DataPanel>
      <DataPanelBody padded={false} className="p-0">
        {loading ? (
          <p className="p-4 text-sm text-muted-foreground">{t.core.common.loading}</p>
        ) : (
          <>
            <ConfiguredProvidersList
              rows={endpoints}
              providerLabels={providerLabels}
              selectedId={selectedId}
              busyId={busyId}
              onSelect={selectEndpoint}
              onAddNew={startAddProvider}
              onRemove={removeEndpoint}
            />
            <ModelCredentialsForm
              kind={kind}
              editing={editing}
              onSaved={async (saved) => {
                await load();
                setEditing(saved);
                setSelectedId(saved.id);
              }}
            />
          </>
        )}
      </DataPanelBody>
    </DataPanel>
  );
}
