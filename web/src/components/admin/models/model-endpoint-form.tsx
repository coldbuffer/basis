import { zodResolver } from '@hookform/resolvers/zod';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { toast } from 'sonner';
import { z } from 'zod';
import { Button } from '@/components/ui/button.js';
import { Checkbox } from '@/components/ui/checkbox.js';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form.js';
import { Input } from '@/components/ui/input.js';
import { Label } from '@/components/ui/label.js';
import { resourceCardSurfaceClass } from '@/lib/ui-classes/card-surface.js';
import { useI18n } from '@/i18n/context.js';
import { fmt } from '@/i18n/format.js';
import { openApiGET, openApiPOST } from '@/lib/openapi/client.js';
import { useApiErrorMessage } from '@/lib/errors/use-api-error-message.js';
import { cn } from '@/lib/utils.js';
import { ModelProviderIcon } from '@/components/admin/models/model-provider-icon.js';
import type { ModelKind } from '@/components/admin/models/model-endpoint-panel.js';

type ProviderInfo = {
  id: string;
  label: string;
  default_api_base: string;
  api_base_editable: boolean;
  api_key_url: string | null;
  models: Array<{ name: string; display_name: string; model: string }>;
};

type RemoteModel = { id: string; name: string; display_name: string };

function providerLabel(
  provider: ProviderInfo,
  labels: Record<string, string> | undefined,
): string {
  return labels?.[provider.id] ?? provider.label;
}

type Props = {
  kind: ModelKind;
  onCreated: () => void;
  onCancel?: () => void;
};

type EndpointFormValues = {
  providerId: string;
  apiKey: string;
  apiBase: string;
};

export function ModelEndpointForm({ kind, onCreated, onCancel }: Props) {
  const { t } = useI18n();
  const apiError = useApiErrorMessage();
  const m = t.admin_models.page;
  const emptyCell = t.core.common.emptyCell;
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [remoteModels, setRemoteModels] = useState<RemoteModel[]>([]);
  const [customModelIds, setCustomModelIds] = useState<string[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());
  const [customModelInput, setCustomModelInput] = useState('');
  const [fetching, setFetching] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [modelSelectionError, setModelSelectionError] = useState<string | null>(null);

  const formSchema = useMemo(
    () =>
      z.object({
        providerId: z.string().min(1),
        apiKey: z.string(),
        apiBase: z.string(),
      }).superRefine((data, ctx) => {
        if (data.providerId === 'custom' && !data.apiBase.trim()) {
          ctx.addIssue({ code: 'custom', message: m.api_base_required, path: ['apiBase'] });
        }
      }),
    [m.api_base_required],
  );

  const form = useForm<EndpointFormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      providerId: 'openai',
      apiKey: '',
      apiBase: '',
    },
  });

  const providerId = form.watch('providerId');
  const apiBase = form.watch('apiBase');

  const selected = useMemo(
    () => providers.find((p) => p.id === providerId) ?? providers[0],
    [providers, providerId],
  );

  const modelOptions = useMemo(() => {
    const map = new Map<string, string>();
    for (const item of remoteModels) {
      map.set(item.id, item.display_name || item.id);
    }
    for (const id of customModelIds) {
      if (!map.has(id)) map.set(id, id);
    }
    return [...map.entries()].map(([id, label]) => ({ id, label }));
  }, [remoteModels, customModelIds]);

  const probeModels = useCallback(
    async (opts?: { silent?: boolean }) => {
      setLoadError(null);
      setFetching(true);
      const values = form.getValues();
      try {
        const data = await openApiPOST<{
          ok: boolean;
          error?: string;
          models?: RemoteModel[];
        }>('/api/v1/model-providers/probe', {
          body: {
            kind,
            provider: values.providerId,
            api_key: values.apiKey.trim(),
            api_base: values.apiBase.trim(),
          },
        });
        if (!data.ok) {
          setRemoteModels([]);
          setLoadError(data.error ?? m.probe_failed);
          return;
        }
        setRemoteModels(data.models ?? []);
        if (!opts?.silent) {
          toast.success(m.probe_success);
        }
      } catch (err) {
        setRemoteModels([]);
        setLoadError(apiError(err));
      } finally {
        setFetching(false);
      }
    },
    [kind, form, m.probe_failed, m.probe_success, apiError],
  );

  useEffect(() => {
    openApiGET<{ providers: ProviderInfo[] }>('/api/v1/model-providers', {
      params: { query: { kind } },
    })
      .then((body) => {
        setProviders(body.providers);
        const first = body.providers[0];
        if (first) {
          form.setValue('providerId', first.id);
          form.setValue('apiBase', first.default_api_base);
        }
      })
      .catch((err) => setLoadError(apiError(err)));
  }, [kind, apiError, form]);

  const selectProvider = useCallback(
    (id: string) => {
      const p = providers.find((x) => x.id === id);
      if (!p) return;
      form.setValue('providerId', p.id);
      form.setValue('apiBase', p.default_api_base);
      setRemoteModels([]);
      setCustomModelIds([]);
      setSelectedIds(new Set());
      setLoadError(null);
      setModelSelectionError(null);
    },
    [providers, form],
  );

  useEffect(() => {
    if (!providerId) return;
    const base = apiBase.trim() || selected?.default_api_base || '';
    if (!base && providerId === 'custom') return;
    const timer = window.setTimeout(() => {
      void probeModels({ silent: true });
    }, 280);
    return () => window.clearTimeout(timer);
  }, [providerId, apiBase, kind, selected?.default_api_base, probeModels]);

  function toggleModel(id: string, checked: boolean) {
    setModelSelectionError(null);
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  function selectAllModels() {
    setModelSelectionError(null);
    setSelectedIds(new Set(modelOptions.map((opt) => opt.id)));
  }

  function clearModelSelection() {
    setSelectedIds(new Set());
  }

  function addCustomModelId() {
    const trimmed = customModelInput.trim();
    if (!trimmed) return;
    setCustomModelIds((prev) => (prev.includes(trimmed) ? prev : [...prev, trimmed]));
    setSelectedIds((prev) => new Set(prev).add(trimmed));
    setCustomModelInput('');
    setModelSelectionError(null);
  }

  async function onSubmit(values: EndpointFormValues) {
    const ids = [...selectedIds].map((id) => id.trim()).filter(Boolean);
    if (ids.length === 0) {
      setModelSelectionError(m.model_required);
      return;
    }
    const base = values.apiBase.trim() || selected?.default_api_base || '';
    setSaving(true);
    setLoadError(null);
    setModelSelectionError(null);
    try {
      const apiKey = values.apiKey.trim();
      const result = await openApiPOST<{ models: unknown[]; skipped?: string[] }>(
        '/api/v1/models/batch',
        {
          body: {
            kind,
            provider: values.providerId,
            api_base: base,
            models: ids,
            api_key: apiKey,
          },
        },
      );
      const added = result.models?.length ?? ids.length;
      toast.success(fmt(m.batch_added_toast, { count: String(added) }));
      onCreated();
    } catch (err) {
      const message = apiError(err);
      setLoadError(message);
      toast.error(message);
    } finally {
      setSaving(false);
    }
  }

  const providerLabels = m.providers as Record<string, string>;
  const selectedCount = selectedIds.size;

  return (
    <Form {...form}>
      <form className="space-y-4" onSubmit={form.handleSubmit(onSubmit)}>
        <div className="space-y-2">
          <Label>{m.provider}</Label>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {providers.map((provider) => (
              <Button
                key={provider.id}
                type="button"
                variant="ghost"
                className={cn(
                  resourceCardSurfaceClass,
                  'h-auto flex items-center gap-2 rounded-xl border px-3 py-2 text-left text-sm font-medium transition-colors',
                  providerId === provider.id
                    ? 'border-[var(--acc)] bg-accent/80'
                    : 'border-transparent hover:border-foreground/15 hover:bg-accent/50',
                )}
                onClick={() => selectProvider(provider.id)}
              >
                <ModelProviderIcon providerId={provider.id} size={20} className="size-6" />
                <span className="min-w-0 truncate">{providerLabel(provider, providerLabels)}</span>
              </Button>
            ))}
          </div>
        </div>

        <FormField
          control={form.control}
          name="apiKey"
          render={({ field }) => (
            <FormItem>
              <div className="flex items-center justify-between gap-2">
                <FormLabel htmlFor={`${kind}-add-api-key`}>{m.field_api_key}</FormLabel>
                {selected?.api_key_url ? (
                  <a
                    href={selected.api_key_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[12px] text-muted-foreground underline underline-offset-2 hover:text-foreground"
                  >
                    {m.get_api_key}
                  </a>
                ) : null}
              </div>
              <FormControl>
                <Input
                  id={`${kind}-add-api-key`}
                  type="password"
                  autoComplete="new-password"
                  placeholder={m.api_key_placeholder}
                  {...field}
                  onBlur={(e) => {
                    field.onBlur();
                    void probeModels({ silent: true });
                  }}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {selected?.api_base_editable ? (
          <FormField
            control={form.control}
            name="apiBase"
            render={({ field }) => (
              <FormItem>
                <FormLabel htmlFor={`${kind}-add-api-base`}>{m.field_base_url}</FormLabel>
                <FormControl>
                  <Input
                    id={`${kind}-add-api-base`}
                    placeholder={m.api_base_placeholder}
                    autoComplete="off"
                    {...field}
                  />
                </FormControl>
                <p className="text-[12px] text-muted-foreground">{m.api_base_hint}</p>
                <FormMessage />
              </FormItem>
            )}
          />
        ) : (
          <p className="text-[12px] text-muted-foreground">
            {m.field_base_url}:{' '}
            <span className="font-mono text-foreground">
              {apiBase || selected?.default_api_base || emptyCell}
            </span>
          </p>
        )}

        <div className="space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Label>{m.models_select_label}</Label>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[12px] text-muted-foreground">
                {fmt(m.models_selected, { count: String(selectedCount) })}
              </span>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs"
                disabled={modelOptions.length === 0}
                onClick={selectAllModels}
              >
                {m.select_all_models}
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs"
                disabled={selectedCount === 0}
                onClick={clearModelSelection}
              >
                {m.clear_model_selection}
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-7"
                disabled={fetching}
                onClick={() => void probeModels()}
              >
                {fetching ? m.fetching_models : m.fetch_models}
              </Button>
            </div>
          </div>

          <div
            className={cn(
              resourceCardSurfaceClass,
              'max-h-52 overflow-y-auto rounded-xl border p-2',
            )}
          >
            {fetching && modelOptions.length === 0 ? (
              <p className="px-2 py-3 text-sm text-muted-foreground">{m.fetching_models}</p>
            ) : modelOptions.length === 0 ? (
              <p className="px-2 py-3 text-sm text-muted-foreground">{m.models_fetch_empty}</p>
            ) : (
              <ul className="space-y-1">
                {modelOptions.map((opt) => (
                  <li key={opt.id}>
                    <label
                      className="flex cursor-pointer items-start gap-2 rounded-md px-2 py-1.5 hover:bg-accent/50"
                    >
                      <Checkbox
                        checked={selectedIds.has(opt.id)}
                        onCheckedChange={(checked) => toggleModel(opt.id, checked === true)}
                        className="mt-0.5"
                      />
                      <span className="min-w-0">
                        <span className="block text-sm leading-snug">{opt.label}</span>
                        {opt.label !== opt.id ? (
                          <span className="block truncate font-mono text-[11px] text-muted-foreground">
                            {opt.id}
                          </span>
                        ) : null}
                      </span>
                    </label>
                  </li>
                ))}
              </ul>
            )}
          </div>
          {modelSelectionError ? (
            <p className="text-sm text-destructive">{modelSelectionError}</p>
          ) : null}
        </div>

        <div className="flex flex-wrap items-end gap-2">
          <div className="min-w-[min(100%,14rem)] flex-1 space-y-1.5">
            <Label htmlFor={`${kind}-add-model-custom`}>{m.custom_model}</Label>
            <Input
              id={`${kind}-add-model-custom`}
              placeholder={m.manual_model_placeholder}
              autoComplete="off"
              value={customModelInput}
              onChange={(e) => setCustomModelInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  addCustomModelId();
                }
              }}
            />
            <p className="text-[12px] text-muted-foreground">{m.manual_model_hint}</p>
          </div>
          <Button type="button" variant="outline" onClick={addCustomModelId}>
            {m.add_custom_model_id}
          </Button>
        </div>

        {loadError ? <p className="text-sm text-destructive">{loadError}</p> : null}

        <div className="flex justify-end gap-2 pt-2">
          {onCancel ? (
            <Button type="button" variant="ghost" onClick={onCancel}>
              {t.core.common.cancel}
            </Button>
          ) : null}
          <Button type="submit" disabled={saving || selectedCount === 0}>
            {fmt(m.add_models_confirm, { count: String(selectedCount) })}
          </Button>
        </div>
      </form>
    </Form>
  );
}
