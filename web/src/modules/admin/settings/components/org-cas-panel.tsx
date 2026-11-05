import { zodResolver } from '@hookform/resolvers/zod';
import { useCallback, useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { toast } from 'sonner';
import { z } from 'zod';
import { Button } from '@/components/ui/button.js';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.js';
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form.js';
import { Input } from '@/components/ui/input.js';
import { Spinner } from '@/components/ui/spinner.js';
import { Switch } from '@/components/ui/switch.js';
import { useI18n } from '@/i18n/context.js';
import type { Locale } from '@/i18n/locale.js';
import { formatUserFacingApiError } from '@/lib/errors/api-error-message.js';
import { openApiGET, openApiPUT } from '@/lib/openapi/client.js';

type OrgPublic = { id: string; name: string; slug: string };

type OrgCasResponse = {
  configured: boolean;
  can_edit?: boolean;
  organization: OrgPublic;
  login_url: string;
  service_url: string;
  server_url?: string;
  login_path?: string;
  validate_path?: string;
  email_attribute?: string;
  email_domains?: string[];
  enabled?: boolean;
};

const casPath = z.string().regex(/^\/(?:[A-Za-z0-9._~-]+\/)*[A-Za-z0-9._~-]+\/?$/);

const casFormSchema = z.object({
  serverUrl: z.string().min(1),
  loginPath: casPath,
  validatePath: casPath,
  emailAttribute: z.string().min(1),
  emailDomains: z.string(),
  enabled: z.boolean(),
});

type CasFormValues = z.infer<typeof casFormSchema>;

const emptyValues: CasFormValues = {
  serverUrl: '',
  loginPath: '/login',
  validatePath: '/serviceValidate',
  emailAttribute: 'email',
  emailDomains: '',
  enabled: true,
};

export function OrgCasPanel({ organizationId }: { organizationId: string | null | undefined }) {
  const { t, locale } = useI18n();
  const copy = t.settings.org_cas;
  const oidcCopy = t.settings.org_sso;
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [data, setData] = useState<OrgCasResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const form = useForm<CasFormValues>({
    resolver: zodResolver(casFormSchema),
    defaultValues: emptyValues,
  });

  const refresh = useCallback(async () => {
    if (!organizationId) {
      setData(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const body = await openApiGET<OrgCasResponse>('/api/v1/orgs/{org_id}/cas', {
        params: { path: { org_id: organizationId } },
      });
      setData(body);
      form.reset(
        body.configured
          ? {
              serverUrl: body.server_url ?? '',
              loginPath: body.login_path || '/login',
              validatePath: body.validate_path || '/serviceValidate',
              emailAttribute: body.email_attribute ?? 'email',
              emailDomains: (body.email_domains ?? []).join(', '),
              enabled: body.enabled ?? true,
            }
          : emptyValues,
      );
    } catch (err) {
      setError(formatUserFacingApiError(err, locale as Locale));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [form, locale, organizationId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const canEdit = data?.can_edit === true;

  async function onSubmit(values: CasFormValues) {
    if (!organizationId || !canEdit) return;
    setSaving(true);
    setError(null);
    const domains = values.emailDomains
      .split(',')
      .map((domain) => domain.trim())
      .filter(Boolean);
    try {
      await openApiPUT('/api/v1/orgs/{org_id}/cas', {
        params: { path: { org_id: organizationId } },
        body: {
          server_url: values.serverUrl,
          login_path: values.loginPath,
          validate_path: values.validatePath,
          email_attribute: values.emailAttribute,
          email_domains: domains,
          enabled: values.enabled,
        },
      });
      toast.success(copy.saved);
      await refresh();
    } catch (err) {
      setError(formatUserFacingApiError(err, locale as Locale));
    } finally {
      setSaving(false);
    }
  }

  function copyText(text: string) {
    void navigator.clipboard.writeText(text).then(() => toast.success(oidcCopy.copied));
  }

  const serviceUrl = data?.service_url ?? '';
  const loginUrl = data?.login_url ?? '';

  if (!organizationId) return null;

  if (loading) {
    return (
      <Card data-testid="org-cas-panel">
        <CardHeader>
          <CardTitle className="text-base">{copy.title}</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner className="size-4" />
          {t.core.common.loading}
        </CardContent>
      </Card>
    );
  }

  if (!data) {
    return (
      <Card data-testid="org-cas-panel">
        <CardHeader>
          <CardTitle className="text-base">{copy.title}</CardTitle>
          <CardDescription>{oidcCopy.load_failed}</CardDescription>
        </CardHeader>
        {error ? <CardContent className="text-sm text-destructive">{error}</CardContent> : null}
      </Card>
    );
  }

  return (
    <Card data-testid="org-cas-panel">
      <CardHeader>
        <CardTitle className="text-base">{copy.title}</CardTitle>
        <CardDescription>{copy.description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        <dl className="grid gap-2 text-sm sm:grid-cols-[minmax(8rem,auto)_1fr]">
          <dt className="text-muted-foreground">{copy.service_url_label}</dt>
          <dd className="flex flex-wrap items-center gap-2">
            <code className="break-all text-xs">{serviceUrl}</code>
            <Button type="button" size="sm" variant="outline" onClick={() => copyText(serviceUrl)}>
              {t.core.common.copy}
            </Button>
          </dd>
          <dt className="text-muted-foreground">{copy.login_url_label}</dt>
          <dd className="flex flex-wrap items-center gap-2">
            <code className="break-all text-xs">{loginUrl}</code>
            <Button type="button" size="sm" variant="outline" onClick={() => copyText(loginUrl)}>
              {t.core.common.copy}
            </Button>
          </dd>
        </dl>
        <p className="text-sm text-muted-foreground">{copy.service_url_hint}</p>
        <p className="text-sm text-muted-foreground">
          {data.configured ? copy.configured : copy.not_configured}
        </p>
        {!canEdit ? (
          <p className="text-sm text-muted-foreground">{oidcCopy.forbidden}</p>
        ) : (
          <Form {...form}>
            <form className="space-y-4" onSubmit={form.handleSubmit(onSubmit)}>
              <FormField
                control={form.control}
                name="serverUrl"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{copy.fields.server_url}</FormLabel>
                    <FormControl>
                      <Input placeholder={copy.server_url_placeholder} {...field} />
                    </FormControl>
                    <FormDescription>{copy.server_url_hint}</FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="loginPath"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{copy.fields.login_path}</FormLabel>
                    <FormControl>
                      <Input className="font-mono" placeholder={copy.login_path_placeholder} {...field} />
                    </FormControl>
                    <FormDescription>{copy.path_hint}</FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="validatePath"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{copy.fields.validate_path}</FormLabel>
                    <FormControl>
                      <Input className="font-mono" placeholder={copy.validate_path_placeholder} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="emailAttribute"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{copy.fields.email_attribute}</FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormDescription>{copy.email_attribute_hint}</FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="emailDomains"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{copy.fields.email_domains}</FormLabel>
                    <FormControl>
                      <Input placeholder="school.edu" {...field} />
                    </FormControl>
                    <FormDescription>{oidcCopy.email_domains_hint}</FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="enabled"
                render={({ field }) => (
                  <FormItem className="flex items-center gap-3 space-y-0">
                    <FormControl>
                      <Switch checked={field.value} onCheckedChange={field.onChange} />
                    </FormControl>
                    <FormLabel className="font-normal">{copy.fields.enabled}</FormLabel>
                  </FormItem>
                )}
              />
              <Button type="submit" disabled={saving}>
                {saving ? copy.saving : copy.save}
              </Button>
            </form>
          </Form>
        )}
      </CardContent>
    </Card>
  );
}
