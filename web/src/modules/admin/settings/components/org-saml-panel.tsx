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
import { Textarea } from '@/components/ui/textarea.js';
import { Spinner } from '@/components/ui/spinner.js';
import { Switch } from '@/components/ui/switch.js';
import { useI18n } from '@/i18n/context.js';
import type { Locale } from '@/i18n/locale.js';
import { openApiGET, openApiPUT } from '@/lib/openapi/client.js';
import { formatUserFacingApiError } from '@/lib/errors/api-error-message.js';

type OrgPublic = { id: string; name: string; slug: string };

type OrgSamlResponse = {
  configured: boolean;
  can_edit?: boolean;
  organization: OrgPublic;
  login_url: string;
  acs_url: string;
  slo_url?: string;
  logout_url_template?: string;
  metadata_url: string;
  idp_slo_url?: string | null;
  slo_enabled?: boolean;
  idp_entity_id?: string;
  idp_sso_url?: string;
  sp_entity_id?: string | null;
  email_domains?: string[];
  enabled?: boolean;
  auth_policy?: string;
  authn_requests_signed?: boolean;
  sp_signing_configured?: boolean;
};

const samlFormSchema = z.object({
  idpEntityId: z.string().min(1),
  idpSsoUrl: z.string().min(1),
  idpCert: z.string(),
  spEntityId: z.string(),
  emailDomains: z.string(),
  enabled: z.boolean(),
  authPolicy: z.enum(['password_allowed', 'sso_preferred', 'sso_required']),
  authnRequestsSigned: z.boolean(),
  spCert: z.string(),
  spPrivateKey: z.string(),
  idpSloUrl: z.string(),
  sloEnabled: z.boolean(),
});

type SamlFormValues = z.infer<typeof samlFormSchema>;

function samlSchema(configured: boolean, signingConfigured: boolean) {
  return samlFormSchema.superRefine((data, ctx) => {
    if (!configured && !data.idpCert.trim()) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['idpCert'], message: 'Required' });
    }
    if (data.authnRequestsSigned) {
      const hasCert = Boolean(data.spCert.trim() || (configured && signingConfigured));
      const hasKey = Boolean(data.spPrivateKey.trim() || (configured && signingConfigured));
      if (!hasCert) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['spCert'], message: 'Required' });
      }
      if (!hasKey) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['spPrivateKey'], message: 'Required' });
      }
    }
    if (data.sloEnabled && !data.idpSloUrl.trim()) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['idpSloUrl'], message: 'Required' });
    }
  });
}

const emptyValues: SamlFormValues = {
  idpEntityId: '',
  idpSsoUrl: '',
  idpCert: '',
  spEntityId: '',
  emailDomains: '',
  enabled: true,
  authPolicy: 'password_allowed',
  authnRequestsSigned: false,
  spCert: '',
  spPrivateKey: '',
  idpSloUrl: '',
  sloEnabled: false,
};

export function OrgSamlPanel({ organizationId }: { organizationId: string | null | undefined }) {
  const { t, locale } = useI18n();
  const copy = t.settings.org_saml;
  const oidcCopy = t.settings.org_sso;
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [data, setData] = useState<OrgSamlResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const configured = data?.configured === true;
  const signingConfigured = data?.sp_signing_configured === true;
  const resolver = useMemo(
    () => zodResolver(samlSchema(configured, signingConfigured)),
    [configured, signingConfigured],
  );
  const form = useForm<SamlFormValues>({
    resolver,
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
      const body = await openApiGET<OrgSamlResponse>('/api/v1/orgs/{org_id}/saml', {
        params: { path: { org_id: organizationId } },
      });
      setData(body);
      if (body.configured) {
        form.reset({
          idpEntityId: body.idp_entity_id ?? '',
          idpSsoUrl: body.idp_sso_url ?? '',
          idpCert: '',
          spEntityId: body.sp_entity_id ?? '',
          emailDomains: (body.email_domains ?? []).join(', '),
          enabled: body.enabled ?? true,
          authPolicy:
            (body.auth_policy as SamlFormValues['authPolicy']) ?? 'password_allowed',
          authnRequestsSigned: body.authn_requests_signed ?? false,
          spCert: '',
          spPrivateKey: '',
          idpSloUrl: body.idp_slo_url ?? '',
          sloEnabled: body.slo_enabled ?? false,
        });
      } else {
        form.reset(emptyValues);
      }
    } catch (err) {
      setError(formatUserFacingApiError(err, locale as Locale));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [organizationId, locale, form]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function onSubmit(values: SamlFormValues) {
    if (!organizationId || !data?.can_edit) return;
    setSaving(true);
    setError(null);
    const domains = values.emailDomains
      .split(',')
      .map((d) => d.trim())
      .filter(Boolean);
    try {
      await openApiPUT('/api/v1/orgs/{org_id}/saml', {
        params: { path: { org_id: organizationId } },
        body: {
          idp_entity_id: values.idpEntityId,
          idp_sso_url: values.idpSsoUrl,
          idp_x509_cert: values.idpCert,
          sp_entity_id: values.spEntityId,
          email_domains: domains,
          enabled: values.enabled,
          auth_policy: values.authPolicy,
          authn_requests_signed: values.authnRequestsSigned,
          sp_x509_cert: values.spCert,
          sp_private_key: values.spPrivateKey,
          idp_slo_url: values.idpSloUrl,
          slo_enabled: values.sloEnabled,
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

  if (!organizationId) return null;
  if (loading) {
    return (
      <Card data-testid="org-saml-panel">
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
      <Card data-testid="org-saml-panel">
        <CardHeader>
          <CardTitle className="text-base">{copy.title}</CardTitle>
          <CardDescription>{oidcCopy.load_failed}</CardDescription>
        </CardHeader>
        {error ? <CardContent className="text-sm text-destructive">{error}</CardContent> : null}
      </Card>
    );
  }

  const canEdit = data.can_edit === true;

  return (
    <Card data-testid="org-saml-panel">
      <CardHeader>
        <CardTitle className="text-base">{copy.title}</CardTitle>
        <CardDescription>{copy.description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        <dl className="grid gap-2 text-sm sm:grid-cols-[minmax(8rem,auto)_1fr]">
          <dt className="text-muted-foreground">{copy.metadata_url_label}</dt>
          <dd className="flex flex-wrap items-center gap-2">
            <code className="break-all text-xs">{data.metadata_url}</code>
            <Button type="button" size="sm" variant="outline" onClick={() => copyText(data.metadata_url)}>
              {t.core.common.copy}
            </Button>
          </dd>
          <dt className="text-muted-foreground">{copy.acs_url_label}</dt>
          <dd className="flex flex-wrap items-center gap-2">
            <code className="break-all text-xs">{data.acs_url}</code>
            <Button type="button" size="sm" variant="outline" onClick={() => copyText(data.acs_url)}>
              {t.core.common.copy}
            </Button>
          </dd>
          <dt className="text-muted-foreground">{copy.login_url_label}</dt>
          <dd className="flex flex-wrap items-center gap-2">
            <code className="break-all text-xs">{data.login_url}</code>
            <Button type="button" size="sm" variant="outline" onClick={() => copyText(data.login_url)}>
              {t.core.common.copy}
            </Button>
          </dd>
          {data.slo_url ? (
            <>
              <dt className="text-muted-foreground">{copy.slo_url_label}</dt>
              <dd className="flex flex-wrap items-center gap-2">
                <code className="break-all text-xs">{data.slo_url}</code>
                <Button type="button" size="sm" variant="outline" onClick={() => copyText(data.slo_url!)}>
                  {t.core.common.copy}
                </Button>
              </dd>
            </>
          ) : null}
          {data.logout_url_template ? (
            <>
              <dt className="text-muted-foreground">{copy.logout_url_template_label}</dt>
              <dd className="flex flex-wrap items-center gap-2">
                <code className="break-all text-xs">{data.logout_url_template}</code>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => copyText(data.logout_url_template!)}
                >
                  {t.core.common.copy}
                </Button>
              </dd>
            </>
          ) : null}
        </dl>
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
                name="idpEntityId"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{copy.fields.idp_entity_id}</FormLabel>
                    <FormControl>
                      <Input placeholder={copy.idp_entity_placeholder} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="idpSsoUrl"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{copy.fields.idp_sso_url}</FormLabel>
                    <FormControl>
                      <Input placeholder={copy.idp_sso_placeholder} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="idpCert"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{copy.fields.idp_cert}</FormLabel>
                    <FormControl>
                      <Textarea
                        className="min-h-[6rem] font-mono text-xs"
                        placeholder={copy.cert_placeholder}
                        {...field}
                      />
                    </FormControl>
                    {data.configured ? (
                      <FormDescription>{copy.cert_keep_hint}</FormDescription>
                    ) : null}
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="spEntityId"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{copy.fields.sp_entity_id}</FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormDescription>{copy.sp_entity_hint}</FormDescription>
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
                      <Input placeholder="acme.com" {...field} />
                    </FormControl>
                    <FormDescription>{oidcCopy.email_domains_hint}</FormDescription>
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
                        <option value="password_allowed">{oidcCopy.auth_policy_password_allowed}</option>
                        <option value="sso_preferred">{oidcCopy.auth_policy_sso_preferred}</option>
                        <option value="sso_required">{oidcCopy.auth_policy_sso_required}</option>
                      </select>
                    </FormControl>
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
              <FormField
                control={form.control}
                name="sloEnabled"
                render={({ field }) => (
                  <FormItem className="flex items-center gap-3 space-y-0">
                    <FormControl>
                      <Switch checked={field.value} onCheckedChange={field.onChange} />
                    </FormControl>
                    <FormLabel className="font-normal">{copy.fields.slo_enabled}</FormLabel>
                  </FormItem>
                )}
              />
              <p className="text-xs text-muted-foreground">{copy.slo_enabled_hint}</p>
              <FormField
                control={form.control}
                name="idpSloUrl"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{copy.fields.idp_slo_url}</FormLabel>
                    <FormControl>
                      <Input placeholder={copy.idp_slo_placeholder} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="authnRequestsSigned"
                render={({ field }) => (
                  <FormItem className="flex items-center gap-3 space-y-0">
                    <FormControl>
                      <Switch checked={field.value} onCheckedChange={field.onChange} />
                    </FormControl>
                    <FormLabel className="font-normal">{copy.fields_sign.authn_requests_signed}</FormLabel>
                  </FormItem>
                )}
              />
              <p className="text-xs text-muted-foreground">{copy.authn_requests_signed_hint}</p>
              <FormField
                control={form.control}
                name="spCert"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{copy.fields_sign.sp_cert}</FormLabel>
                    <FormControl>
                      <Textarea
                        className="min-h-[5rem] font-mono text-xs"
                        placeholder={copy.cert_placeholder}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="spPrivateKey"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{copy.fields_sign.sp_private_key}</FormLabel>
                    <FormControl>
                      <Textarea
                        className="min-h-[5rem] font-mono text-xs"
                        autoComplete="off"
                        {...field}
                      />
                    </FormControl>
                    {data.configured && signingConfigured ? (
                      <FormDescription>{copy.sp_private_key_keep_hint}</FormDescription>
                    ) : null}
                    <FormMessage />
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
