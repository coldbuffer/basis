import { zodResolver } from '@hookform/resolvers/zod';
import { useCallback, useEffect, useMemo, useState } from 'react';
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
import { openApiGET, openApiPUT } from '@/lib/openapi/client.js';
import { formatUserFacingApiError } from '@/lib/errors/api-error-message.js';
import { orgSsoPublicUrls } from '@/lib/session/auth-site-url.js';

type OrgPublic = { id: string; name: string; slug: string };

type OrgOidcResponse = {
  configured: boolean;
  can_edit?: boolean;
  organization: OrgPublic;
  login_url: string;
  callback_url: string;
  issuer?: string;
  client_id?: string;
  scopes?: string;
  email_domains?: string[];
  enabled?: boolean;
  auth_policy?: string;
};

const orgSsoFormSchema = z.object({
  issuer: z.string().min(1),
  clientId: z.string().min(1),
  clientSecret: z.string(),
  scopes: z.string(),
  emailDomains: z.string(),
  enabled: z.boolean(),
  authPolicy: z.enum(['password_allowed', 'sso_preferred', 'sso_required']),
});

type OrgSsoFormValues = z.infer<typeof orgSsoFormSchema>;

function orgSsoSchema(configured: boolean) {
  return orgSsoFormSchema.superRefine((data, ctx) => {
    if (!configured && !data.clientSecret.trim()) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['clientSecret'],
        message: 'Required',
      });
    }
  });
}

const emptyOrgSsoValues: OrgSsoFormValues = {
  issuer: '',
  clientId: '',
  clientSecret: '',
  scopes: 'openid email profile',
  emailDomains: '',
  enabled: true,
  authPolicy: 'password_allowed',
};

export function OrgSsoPanel({
  organizationId,
  siteBaseUrl,
}: {
  organizationId: string | null | undefined;
  siteBaseUrl?: string;
}) {
  const { t, locale } = useI18n();
  const copy = t.settings.org_sso;
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [data, setData] = useState<OrgOidcResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const configured = data?.configured === true;
  const resolver = useMemo(() => zodResolver(orgSsoSchema(configured)), [configured]);

  const form = useForm<OrgSsoFormValues>({
    resolver,
    defaultValues: emptyOrgSsoValues,
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
      const body = await openApiGET<OrgOidcResponse>('/api/v1/orgs/{org_id}/oidc', {
        params: { path: { org_id: organizationId } },
      });
      setData(body);
      if (body.configured) {
        form.reset({
          issuer: body.issuer ?? '',
          clientId: body.client_id ?? '',
          clientSecret: '',
          scopes: body.scopes ?? 'openid email profile',
          emailDomains: (body.email_domains ?? []).join(', '),
          enabled: body.enabled ?? true,
          authPolicy:
            (body.auth_policy as OrgSsoFormValues['authPolicy']) ?? 'password_allowed',
        });
      } else {
        form.reset({ ...emptyOrgSsoValues, clientSecret: '' });
      }
    } catch (err) {
      setError(formatUserFacingApiError(err, locale as Locale));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [organizationId, locale]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function onSubmit(values: OrgSsoFormValues) {
    if (!organizationId || !data?.can_edit) return;
    setSaving(true);
    setError(null);
    const domains = values.emailDomains
      .split(',')
      .map((d) => d.trim())
      .filter(Boolean);
    try {
      await openApiPUT('/api/v1/orgs/{org_id}/oidc', {
        params: { path: { org_id: organizationId } },
        body: {
          issuer: values.issuer,
          client_id: values.clientId,
          client_secret: values.clientSecret,
          scopes: values.scopes,
          email_domains: domains,
          enabled: values.enabled,
          auth_policy: values.authPolicy,
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
    void navigator.clipboard.writeText(text).then(() => {
      toast.success(copy.copied);
    });
  }

  const publicUrls = useMemo(() => {
    const base = siteBaseUrl?.trim();
    const slug = data?.organization.slug;
    if (!base || !slug) return null;
    return orgSsoPublicUrls(base, slug);
  }, [data?.organization.slug, siteBaseUrl]);

  const loginUrl = publicUrls?.login_url ?? data?.login_url ?? '';
  const callbackUrl = publicUrls?.callback_url ?? data?.callback_url ?? '';

  if (!organizationId) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{copy.title}</CardTitle>
          <CardDescription>{copy.no_organization}</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (loading) {
    return (
      <Card>
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
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{copy.title}</CardTitle>
          <CardDescription>{copy.load_failed}</CardDescription>
        </CardHeader>
        {error ? <CardContent className="text-sm text-destructive">{error}</CardContent> : null}
      </Card>
    );
  }

  const canEdit = data.can_edit === true;
  const readOnly = !canEdit;

  return (
    <Card data-testid="org-oidc-panel">
      <CardHeader>
        <CardTitle className="text-base">{copy.title}</CardTitle>
        <CardDescription>{copy.description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {error ? <p className="text-sm text-destructive">{error}</p> : null}

        <dl className="grid gap-2 text-sm sm:grid-cols-[minmax(8rem,auto)_1fr]">
          <dt className="text-muted-foreground">{copy.org_label}</dt>
          <dd>{data.organization.name}</dd>
          <dt className="text-muted-foreground">{copy.slug_label}</dt>
          <dd className="font-mono text-xs">{data.organization.slug}</dd>
          <dt className="text-muted-foreground">{copy.login_url_label}</dt>
          <dd className="flex flex-wrap items-center gap-2">
            <code className="break-all text-xs">{loginUrl}</code>
            <Button type="button" size="sm" variant="outline" onClick={() => copyText(loginUrl)}>
              {t.core.common.copy}
            </Button>
          </dd>
          <dt className="text-muted-foreground">{copy.callback_hint}</dt>
          <dd className="flex flex-wrap items-center gap-2">
            <code className="break-all text-xs">{callbackUrl}</code>
            <Button type="button" size="sm" variant="outline" onClick={() => copyText(callbackUrl)}>
              {t.core.common.copy}
            </Button>
          </dd>
        </dl>
        <p className="text-sm text-muted-foreground">
          {data.configured ? copy.configured : copy.not_configured}
        </p>

        {readOnly ? (
          <p className="text-sm text-muted-foreground">{copy.forbidden}</p>
        ) : (
          <Form {...form}>
            <form className="space-y-4" onSubmit={form.handleSubmit(onSubmit)}>
              <FormField
                control={form.control}
                name="issuer"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{copy.fields.issuer}</FormLabel>
                    <FormControl>
                      <Input placeholder={copy.issuer_placeholder} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="clientId"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{copy.fields.client_id}</FormLabel>
                    <FormControl>
                      <Input placeholder={copy.client_id_placeholder} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="clientSecret"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{copy.fields.client_secret}</FormLabel>
                    <FormControl>
                      <Input type="password" autoComplete="off" placeholder={copy.client_secret_placeholder} {...field} />
                    </FormControl>
                    {data.configured ? (
                      <FormDescription>{copy.client_secret_keep_hint}</FormDescription>
                    ) : null}
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="scopes"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{copy.fields.scopes}</FormLabel>
                    <FormControl>
                      <Input placeholder={copy.scopes_placeholder} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="authPolicy"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{copy.fields.auth_policy}</FormLabel>
                    <FormControl>
                      <select
                        className="native-select native-select--full"
                        value={field.value}
                        onChange={field.onChange}
                      >
                        <option value="password_allowed">{copy.auth_policy_password_allowed}</option>
                        <option value="sso_preferred">{copy.auth_policy_sso_preferred}</option>
                        <option value="sso_required">{copy.auth_policy_sso_required}</option>
                      </select>
                    </FormControl>
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
                      <Input placeholder="acme.com, acme.cn" {...field} />
                    </FormControl>
                    <FormDescription>{copy.email_domains_hint}</FormDescription>
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
