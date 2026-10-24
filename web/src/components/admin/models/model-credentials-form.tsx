import { zodResolver } from '@hookform/resolvers/zod';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { toast } from 'sonner';
import { z } from 'zod';
import type { ConfiguredProviderRow } from '@/components/admin/models/configured-providers-list.js';
import { Button } from '@/components/ui/button.js';
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
import { openApiGET, openApiPOST, openApiPUT } from '@/lib/openapi/client.js';
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
};

function providerLabel(
  provider: ProviderInfo,
  labels: Record<string, string> | undefined,
): string {
  return labels?.[provider.id] ?? provider.label;
}

type Props = {
  kind: ModelKind;
  editing: ConfiguredProviderRow | null;
  onSaved: (row: ConfiguredProviderRow) => void | Promise<void>;
};

type CredentialsFormValues = {
  providerId: string;
  apiKey: string;
  apiBase: string;
};

export function ModelCredentialsForm({ kind, editing, onSaved }: Props) {
  const { t } = useI18n();
  const apiError = useApiErrorMessage();
  const m = t.admin_models.page;
  const emptyCell = t.core.common.emptyCell;
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [testError, setTestError] = useState<string | null>(null);
  const [hasStoredKey, setHasStoredKey] = useState(false);

  const formSchema = useMemo(
    () =>
      z
        .object({
          providerId: z.string().min(1),
          apiKey: z.string(),
          apiBase: z.string(),
        })
        .superRefine((data, ctx) => {
          if (data.providerId === 'custom' && !data.apiBase.trim()) {
            ctx.addIssue({ code: 'custom', message: m.api_base_required, path: ['apiBase'] });
          }
        }),
    [m.api_base_required],
  );

  const form = useForm<CredentialsFormValues>({
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

  const loadProviders = useCallback(async () => {
    setLoadError(null);
    try {
      const providerBody = await openApiGET<{ providers: ProviderInfo[] }>(
        '/api/v1/model-providers',
        { params: { query: { kind } } },
      );
      setProviders(providerBody.providers);
      return providerBody.providers;
    } catch (err) {
      setLoadError(apiError(err));
      return [];
    }
  }, [kind, apiError]);

  useEffect(() => {
    void loadProviders();
  }, [loadProviders]);

  useEffect(() => {
    if (providers.length === 0) return;
    const first = providers[0];
    if (editing) {
      const match = providers.find((p) => p.id === editing.provider) ?? first;
      form.reset({
        providerId: match?.id ?? editing.provider,
        apiBase: editing.api_base || match?.default_api_base || '',
        apiKey: '',
      });
      setHasStoredKey(editing.configured);
    } else {
      form.reset({
        providerId: first.id,
        apiBase: first.default_api_base,
        apiKey: '',
      });
      setHasStoredKey(false);
    }
    setTestError(null);
  }, [editing, providers, form]);

  const selectProvider = useCallback(
    (id: string) => {
      const p = providers.find((x) => x.id === id);
      if (!p) return;
      form.setValue('providerId', p.id);
      form.setValue('apiBase', p.default_api_base);
      setLoadError(null);
      setTestError(null);
    },
    [providers, form],
  );

  async function testApiKey() {
    const values = form.getValues();
    const base = values.apiBase.trim() || selected?.default_api_base || '';
    const key = values.apiKey.trim();
    if (!key && !hasStoredKey) {
      toast.error(m.api_key_test_need_key);
      return;
    }
    setTestError(null);
    setTesting(true);
    try {
      const data = await openApiPOST<{
        ok: boolean;
        error?: string;
        models?: unknown[];
      }>('/api/v1/model-providers/probe', {
        body: {
          kind,
          provider: values.providerId,
          api_key: key,
          api_base: base,
        },
      });
      if (!data.ok) {
        const message = data.error ?? m.probe_failed;
        setTestError(message);
        toast.error(message);
        return;
      }
      const count = data.models?.length ?? 0;
      toast.success(fmt(m.api_key_test_success, { count: String(count) }));
    } catch (err) {
      const message = apiError(err);
      setTestError(message);
      toast.error(message);
    } finally {
      setTesting(false);
    }
  }

  async function onSubmit(values: CredentialsFormValues) {
    const base = values.apiBase.trim() || selected?.default_api_base || '';
    setSaving(true);
    setLoadError(null);
    try {
      const result = await openApiPUT<{ model: ConfiguredProviderRow }>('/api/v1/models/endpoint', {
        body: {
          kind,
          provider: values.providerId,
          api_base: base,
          api_key: values.apiKey.trim(),
        },
      });
      toast.success(m.endpoint_saved_toast);
      setHasStoredKey(true);
      form.setValue('apiKey', '');
      await onSaved({
        id: result.model.id,
        provider: result.model.provider,
        api_base: result.model.api_base,
        configured: result.model.configured,
      });
    } catch (err) {
      const message = apiError(err);
      setLoadError(message);
      toast.error(message);
    } finally {
      setSaving(false);
    }
  }

  const providerLabels = m.providers as Record<string, string>;
  const formTitle = editing ? m.edit_provider_credentials : m.add_provider_credentials;

  return (
    <Form {...form}>
      <form className="mx-auto max-w-xl space-y-4 p-4" onSubmit={form.handleSubmit(onSubmit)}>
        <h3 className="text-sm font-semibold">{formTitle}</h3>
        <p className="text-sm text-muted-foreground">{m.endpoint_credentials_hint}</p>

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
                <FormLabel htmlFor={`${kind}-cred-api-key`}>{m.field_api_key}</FormLabel>
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
              <div className="flex gap-2">
                <FormControl className="flex-1">
                  <Input
                    id={`${kind}-cred-api-key`}
                    type="password"
                    autoComplete="new-password"
                    placeholder={
                      hasStoredKey ? m.api_key_placeholder_configured : m.api_key_placeholder
                    }
                    {...field}
                    onChange={(e) => {
                      field.onChange(e);
                      setTestError(null);
                    }}
                  />
                </FormControl>
                <Button
                  type="button"
                  variant="outline"
                  className="shrink-0"
                  disabled={testing || saving}
                  onClick={() => void testApiKey()}
                >
                  {testing ? m.testing_api_key : m.test_api_key}
                </Button>
              </div>
              {testError ? <p className="text-sm text-destructive">{testError}</p> : null}
              {hasStoredKey ? (
                <p className="text-[12px] text-muted-foreground">{m.api_key_keep_hint}</p>
              ) : null}
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
                <FormLabel htmlFor={`${kind}-cred-api-base`}>{m.field_base_url}</FormLabel>
                <FormControl>
                  <Input
                    id={`${kind}-cred-api-base`}
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

        {loadError ? <p className="text-sm text-destructive">{loadError}</p> : null}

        <div className="flex justify-end pt-2">
          <Button type="submit" disabled={saving}>
            {m.save_endpoint}
          </Button>
        </div>
      </form>
    </Form>
  );
}
