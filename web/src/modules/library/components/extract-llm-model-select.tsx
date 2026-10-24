import { useCallback, useEffect, useRef, useState } from 'react';
import { Label } from '@/components/ui/label.js';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select.js';
import { Spinner } from '@/components/ui/spinner.js';
import { useI18n } from '@/i18n/context.js';
import { useWorkspaceWsClient } from '@/lib/workspace/ws-context.js';
import { ModelProviderIcon } from '@/components/admin/models/model-provider-icon.js';
import { useApiErrorMessage } from '@/lib/errors/use-api-error-message.js';

type LlmProviderRow = { id: string; provider: string; api_base: string };
type RemoteModel = { id: string; name: string; display_name: string };

type Props = {
  workspaceId: string;
  endpointId: string;
  onEndpointIdChange: (id: string) => void;
  modelId: string;
  onModelIdChange: (id: string) => void;
  disabled?: boolean;
  active: boolean;
};

export function ExtractLlmModelSelect({
  workspaceId,
  endpointId,
  onEndpointIdChange,
  modelId,
  onModelIdChange,
  disabled,
  active,
}: Props) {
  const { t } = useI18n();
  const k = t.library.sources;
  const providerLabels = t.admin_models.page.providers as Record<string, string>;
  const apiError = useApiErrorMessage();
  const client = useWorkspaceWsClient();
  const [providers, setProviders] = useState<LlmProviderRow[]>([]);
  const [models, setModels] = useState<RemoteModel[]>([]);
  const [loadingProviders, setLoadingProviders] = useState(false);
  const [loadingModels, setLoadingModels] = useState(false);
  const [providerError, setProviderError] = useState<string | null>(null);
  const [modelError, setModelError] = useState<string | null>(null);
  const modelIdRef = useRef(modelId);
  const endpointIdRef = useRef(endpointId);
  modelIdRef.current = modelId;
  endpointIdRef.current = endpointId;

  const loadProviders = useCallback(async () => {
    if (!active) return;
    setLoadingProviders(true);
    setProviderError(null);
    try {
      const data = await client.processing.listLlmProviders();
      const list = data.providers ?? [];
      setProviders(list);
      if (list.length === 0) {
        onEndpointIdChange('');
        onModelIdChange('');
        return;
      }
      const current = endpointIdRef.current.trim();
      if (!current || !list.some((p) => p.id === current)) {
        onEndpointIdChange(list[0].id);
      }
    } catch (err) {
      setProviders([]);
      setProviderError(apiError(err));
    } finally {
      setLoadingProviders(false);
    }
  }, [active, apiError, client, onEndpointIdChange, onModelIdChange]);

  const loadModels = useCallback(async (forEndpointId: string) => {
    if (!active || !forEndpointId.trim()) {
      setModels([]);
      return;
    }
    setLoadingModels(true);
    setModelError(null);
    try {
      const data = await client.processing.listLlmModels(forEndpointId);
      if (!data.ok) {
        setModels([]);
        setModelError(data.error ?? k.extract_model_fetch_failed);
        onModelIdChange('');
        return;
      }
      const list = data.models ?? [];
      setModels(list);
      if (list.length === 0) {
        onModelIdChange('');
        return;
      }
      const current = modelIdRef.current.trim();
      if (!current || !list.some((m) => m.id === current)) {
        onModelIdChange(list[0].id);
      }
    } catch (err) {
      setModels([]);
      setModelError(apiError(err));
      onModelIdChange('');
    } finally {
      setLoadingModels(false);
    }
  }, [active, apiError, client, k.extract_model_fetch_failed, onModelIdChange]);

  useEffect(() => {
    void loadProviders();
  }, [loadProviders, workspaceId, active]);

  useEffect(() => {
    if (!endpointId.trim()) {
      setModels([]);
      return;
    }
    void loadModels(endpointId);
  }, [endpointId, loadModels, active]);

  function providerLabel(row: LlmProviderRow) {
    const name = providerLabels[row.provider] ?? row.provider;
    return row.api_base ? `${name} · ${row.api_base}` : name;
  }

  if (!active) return null;

  const showModelSelect = !loadingModels && models.length > 0;

  return (
    <div className="space-y-3" data-testid="extract-llm-model-select">
      <div className="space-y-1.5">
        <Label htmlFor="extract-llm-provider">{k.extract_provider_label}</Label>
        {loadingProviders ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Spinner className="size-4" />
            {k.extract_provider_loading}
          </div>
        ) : providers.length > 0 ? (
          <Select
            value={endpointId || undefined}
            onValueChange={(id) => {
              onEndpointIdChange(id);
              onModelIdChange('');
            }}
            disabled={disabled}
          >
            <SelectTrigger id="extract-llm-provider" className="w-full">
              <SelectValue placeholder={k.extract_provider_placeholder} />
            </SelectTrigger>
            <SelectContent>
              {providers.map((row) => (
                <SelectItem key={row.id} value={row.id}>
                  <span className="flex min-w-0 items-center gap-2">
                    <ModelProviderIcon providerId={row.provider} size={16} />
                    <span className="truncate">{providerLabel(row)}</span>
                  </span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : (
          <p className="text-xs text-muted-foreground">
            {providerError ?? k.extract_provider_empty}
          </p>
        )}
      </div>

      {endpointId ? (
        <div className="space-y-1.5">
          <Label htmlFor="extract-llm-model">{k.extract_model_label}</Label>
          {loadingModels ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Spinner className="size-4" />
              {k.extract_model_loading}
            </div>
          ) : showModelSelect ? (
            <Select
              value={modelId || undefined}
              onValueChange={onModelIdChange}
              disabled={disabled}
            >
              <SelectTrigger id="extract-llm-model" className="w-full">
                <SelectValue placeholder={k.extract_model_placeholder} />
              </SelectTrigger>
              <SelectContent>
                {models.map((model) => (
                  <SelectItem key={model.id} value={model.id}>
                    {model.display_name || model.id}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : (
            <p className="text-xs text-muted-foreground">
              {modelError ?? k.extract_model_empty}
            </p>
          )}
        </div>
      ) : null}
    </div>
  );
}
