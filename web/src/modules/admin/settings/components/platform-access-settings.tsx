import { zodResolver } from '@hookform/resolvers/zod';
import { type ComponentProps, type ReactNode, useCallback, useEffect, useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button.js';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.js';
import { Form, FormField } from '@/components/ui/form.js';
import { Input } from '@/components/ui/input.js';
import { Label } from '@/components/ui/label.js';
import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select.js';
import { Spinner } from '@/components/ui/spinner.js';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group.js';
import { Switch } from '@/components/ui/switch.js';
import { useI18n } from '@/i18n/context.js';
import { openApiGET, openApiPUT } from '@/lib/openapi/client.js';
import { useApiErrorMessage } from '@/lib/errors/use-api-error-message.js';
import { normalizeSiteUrl, platformAuthCallbacks } from '@/lib/session/auth-site-url.js';
import { cn } from '@/lib/utils.js';

type ProviderId = 'password' | 'email' | 'github' | 'google';

type AccessSettings = {
  auth_providers: string[];
  signup_policy: 'open' | 'closed';
  magic_link_dev_log: boolean;
  public_url: string;
  web_origin: string;
  callbacks: Record<string, string>;
  credentials: {
    email: {
      transport: 'smtp' | 'resend';
      from: string | null;
      host: string | null;
      port: number | null;
      username: string | null;
      api_key: string | null;
      password: string | null;
    };
    oauth: {
      github: { client_id: string | null; client_secret: string | null };
      google: { client_id: string | null; client_secret: string | null };
    };
  };
};

const platformAccessSchema = z.object({
  providers: z.array(z.string()).min(1),
  signupPolicy: z.enum(['open', 'closed']),
  siteUrl: z.string(),
  magicLinkDevLog: z.boolean(),
  mailTransport: z.enum(['smtp', 'resend']),
  emailFrom: z.string(),
  resendApiKey: z.string(),
  smtpHost: z.string(),
  smtpPort: z.string(),
  smtpUsername: z.string(),
  smtpPassword: z.string(),
  githubClientId: z.string(),
  githubClientSecret: z.string(),
  googleClientId: z.string(),
  googleClientSecret: z.string(),
});

type PlatformAccessFormValues = z.infer<typeof platformAccessSchema>;

const defaultPlatformAccessValues: PlatformAccessFormValues = {
  providers: ['password'],
  signupPolicy: 'open',
  siteUrl: '',
  magicLinkDevLog: false,
  mailTransport: 'resend',
  emailFrom: '',
  resendApiKey: '',
  smtpHost: '',
  smtpPort: '587',
  smtpUsername: '',
  smtpPassword: '',
  githubClientId: '',
  githubClientSecret: '',
  googleClientId: '',
  googleClientSecret: '',
};

function accessToFormValues(data: AccessSettings): PlatformAccessFormValues {
  const site = normalizeSiteUrl(data.web_origin || data.public_url || '');
  const email = data.credentials.email;
  return {
    providers: data.auth_providers,
    signupPolicy: data.signup_policy,
    siteUrl: site,
    magicLinkDevLog: data.magic_link_dev_log,
    mailTransport: email.transport === 'smtp' ? 'smtp' : 'resend',
    emailFrom: email.from ?? '',
    resendApiKey: email.api_key ?? '',
    smtpHost: email.host ?? '',
    smtpPort: email.port != null ? String(email.port) : '587',
    smtpUsername: email.username ?? '',
    smtpPassword: email.password ?? '',
    githubClientId: data.credentials.oauth.github.client_id ?? '',
    githubClientSecret: data.credentials.oauth.github.client_secret ?? '',
    googleClientId: data.credentials.oauth.google.client_id ?? '',
    googleClientSecret: data.credentials.oauth.google.client_secret ?? '',
  };
}

function isEnabled(list: string[], id: ProviderId): boolean {
  return list.includes(id);
}

function setProviderEnabled(list: string[], id: ProviderId, on: boolean): string[] {
  const next = new Set(list);
  if (on) next.add(id);
  else next.delete(id);
  const order: ProviderId[] = ['password', 'email', 'github', 'google'];
  const out = order.filter((p) => next.has(p));
  return out.length > 0 ? out : ['password'];
}

function Field({
  id,
  label,
  hint,
  children,
  className,
}: {
  id: string;
  label: string;
  hint?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('space-y-1.5', className)}>
      <Label htmlFor={id} className="text-[13px] font-medium text-foreground/90">
        {label}
      </Label>
      {children}
      {hint ? <p className="text-xs leading-relaxed text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

function CopyableUrl({ label, url }: { label: string; url: string }) {
  const { t } = useI18n();
  const copyMsg = t.admin_settings.page.access.url_copied;

  function copy() {
    void navigator.clipboard.writeText(url).then(() => toast.success(copyMsg));
  }

  return (
    <div className="rounded-lg border border-border/70 bg-muted/25 px-3 py-2.5">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <div className="mt-1.5 flex flex-wrap items-start gap-2">
        <code className="min-w-0 flex-1 break-all text-[11px] leading-relaxed text-foreground/90">
          {url}
        </code>
        <Button type="button" variant="outline" size="sm" className="h-7 shrink-0 px-2 text-xs" onClick={copy}>
          {t.core.common.copy}
        </Button>
      </div>
    </div>
  );
}

function SecretInput({
  id,
  label,
  ...inputProps
}: {
  id: string;
  label: string;
} & ComponentProps<'input'>) {
  const { t } = useI18n();
  const [visible, setVisible] = useState(false);

  return (
    <Field id={id} label={label}>
      <div className="relative">
        <Input
          id={id}
          type={visible ? 'text' : 'password'}
          autoComplete="off"
          className="h-9 pr-10 font-mono text-sm"
          {...inputProps}
        />
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          className="absolute top-1/2 right-1 -translate-y-1/2 text-muted-foreground"
          aria-label={visible ? t.login.page.hide_password : t.login.page.show_password}
          aria-pressed={visible}
          onClick={() => setVisible((v) => !v)}
        >
          <PublicIcon name={visible ? 'eye-off' : 'eye-open'} size={16} />
        </Button>
      </div>
    </Field>
  );
}

function ProviderBlock({
  title,
  hint,
  enabled,
  onEnabledChange,
  children,
}: {
  title: string;
  hint?: string;
  enabled: boolean;
  onEnabledChange: (on: boolean) => void;
  children?: ReactNode;
}) {
  const { t } = useI18n();
  const copy = t.admin_settings.page.access;

  return (
    <div className="border-t border-border/80 pt-6 first:border-t-0 first:pt-0">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 space-y-0.5">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold tracking-tight">{title}</h3>
            {enabled ? (
              <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-primary">
                {copy.enabled_badge}
              </span>
            ) : null}
          </div>
          {hint ? <p className="text-xs leading-relaxed text-muted-foreground">{hint}</p> : null}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Label htmlFor={`enable-${title}`} className="sr-only">
            {copy.enable_on_login_page}
          </Label>
          <span className="text-xs text-muted-foreground">{copy.enable_on_login_page}</span>
          <Switch id={`enable-${title}`} checked={enabled} onCheckedChange={onEnabledChange} />
        </div>
      </div>
      {children ? (
        <div
          className={cn(
            'mt-4 space-y-4 rounded-lg border border-border/60 bg-muted/15 p-4 transition-opacity',
            !enabled && 'opacity-60',
          )}
        >
          {children}
        </div>
      ) : null}
    </div>
  );
}

function SignupOption({
  value,
  label,
  description,
}: {
  value: 'open' | 'closed';
  label: string;
  description: string;
}) {
  return (
    <label
      className={cn(
        'flex cursor-pointer gap-3 rounded-lg border px-3 py-3 transition-colors',
        'border-border/70 bg-background hover:bg-muted/30',
        'has-[[data-state=checked]]:border-primary/40 has-[[data-state=checked]]:bg-primary/5 has-[[data-state=checked]]:ring-1 has-[[data-state=checked]]:ring-primary/20',
      )}
    >
      <RadioGroupItem value={value} className="mt-0.5" />
      <span className="min-w-0 space-y-0.5">
        <span className="block text-sm font-medium">{label}</span>
        <span className="block text-xs leading-relaxed text-muted-foreground">{description}</span>
      </span>
    </label>
  );
}

export function PlatformAccessSettings({
  onSiteUrlChange,
}: {
  onSiteUrlChange?: (siteUrl: string) => void;
}) {
  const { t } = useI18n();
  const copy = t.admin_settings.page.access;
  const apiError = useApiErrorMessage();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [access, setAccess] = useState<AccessSettings | null>(null);

  const form = useForm<PlatformAccessFormValues>({
    resolver: zodResolver(platformAccessSchema),
    defaultValues: defaultPlatformAccessValues,
  });

  const siteUrl = form.watch('siteUrl');
  const providers = form.watch('providers');
  const mailTransport = form.watch('mailTransport');

  const applyAccess = useCallback(
    (data: AccessSettings) => {
      setAccess(data);
      const values = accessToFormValues(data);
      form.reset(values);
      onSiteUrlChange?.(values.siteUrl);
    },
    [form, onSiteUrlChange],
  );

  useEffect(() => {
    onSiteUrlChange?.(siteUrl);
  }, [onSiteUrlChange, siteUrl]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    openApiGET<AccessSettings>('/api/v1/settings/access')
      .then((data) => {
        if (!cancelled) applyAccess(data);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(apiError(err));
          setAccess(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [apiError, applyAccess]);

  async function onSubmit(values: PlatformAccessFormValues) {
    setSaving(true);
    setError(null);
    const origin = normalizeSiteUrl(values.siteUrl);
    try {
      const data = await openApiPUT<AccessSettings>('/api/v1/settings/access', {
        body: {
          auth_providers: values.providers,
          signup_policy: values.signupPolicy,
          magic_link_dev_log: values.magicLinkDevLog,
          public_url: origin,
          web_origin: origin,
          credentials: {
            email: {
              transport: values.mailTransport,
              from: values.emailFrom.trim() || undefined,
              host: values.smtpHost.trim() || undefined,
              port: values.smtpPort.trim() ? Number(values.smtpPort) : undefined,
              username: values.smtpUsername.trim() || undefined,
              ...(values.smtpPassword.trim() ? { password: values.smtpPassword.trim() } : {}),
              ...(values.resendApiKey.trim() ? { api_key: values.resendApiKey.trim() } : {}),
            },
            oauth: {
              github: {
                ...(values.githubClientId.trim() ? { client_id: values.githubClientId.trim() } : {}),
                ...(values.githubClientSecret.trim()
                  ? { client_secret: values.githubClientSecret.trim() }
                  : {}),
              },
              google: {
                ...(values.googleClientId.trim() ? { client_id: values.googleClientId.trim() } : {}),
                ...(values.googleClientSecret.trim()
                  ? { client_secret: values.googleClientSecret.trim() }
                  : {}),
              },
            },
          },
        },
      });
      applyAccess(data);
      toast.success(t.core.common.save);
    } catch (err) {
      const msg = apiError(err);
      setError(msg);
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  }

  const callbacks = useMemo(
    () => platformAuthCallbacks(siteUrl || access?.public_url || ''),
    [access?.public_url, siteUrl],
  );

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center gap-2 py-10 text-sm text-muted-foreground">
          <Spinner className="size-4" />
          {t.core.common.loading}
        </CardContent>
      </Card>
    );
  }

  if (error && !access) {
    return (
      <Card>
        <CardContent className="py-8 text-sm text-destructive">{error}</CardContent>
      </Card>
    );
  }

  return (
    <Form {...form}>
      <form className="space-y-6" onSubmit={form.handleSubmit(onSubmit)}>
      {error ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      ) : null}

      <Card>
        <CardHeader className="pb-4">
          <CardTitle className="text-base">{copy.form_title}</CardTitle>
          <CardDescription>{copy.form_desc}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <FormField
            control={form.control}
            name="siteUrl"
            render={({ field }) => (
              <Field id="site-url" label={copy.site_url} hint={copy.site_url_hint}>
                <Input
                  id="site-url"
                  className="h-9 font-mono text-sm"
                  placeholder={copy.site_url_placeholder}
                  {...field}
                />
              </Field>
            )}
          />

          {callbacks ? (
            <div className="space-y-2">
              <Label className="text-[13px] font-medium">{copy.callbacks_title}</Label>
              <p className="text-xs text-muted-foreground">{copy.callbacks_desc}</p>
              <div className="grid gap-2">
                <CopyableUrl label={copy.callback_github} url={callbacks.github} />
                <CopyableUrl label={copy.callback_google} url={callbacks.google} />
                <CopyableUrl label={copy.callback_org_oidc} url={callbacks.org_oidc} />
                {callbacks.org_saml_acs ? (
                  <CopyableUrl label={copy.callback_org_saml_acs} url={callbacks.org_saml_acs} />
                ) : null}
                {callbacks.org_saml_slo ? (
                  <CopyableUrl label={copy.callback_org_saml_slo} url={callbacks.org_saml_slo} />
                ) : null}
              </div>
            </div>
          ) : null}

          <div className="space-y-2">
            <Label className="text-[13px] font-medium">{copy.signup_title}</Label>
            <p className="text-xs text-muted-foreground">{copy.signup_desc}</p>
            <FormField
              control={form.control}
              name="signupPolicy"
              render={({ field }) => (
                <RadioGroup
                  value={field.value}
                  onValueChange={field.onChange}
                  className="grid gap-2 sm:grid-cols-2"
                >
                  <SignupOption
                    value="open"
                    label={copy.signup_open_short}
                    description={copy.signup_open_detail}
                  />
                  <SignupOption
                    value="closed"
                    label={copy.signup_closed_short}
                    description={copy.signup_closed_detail}
                  />
                </RadioGroup>
              )}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-4">
          <CardTitle className="text-base">{copy.providers_title}</CardTitle>
          <CardDescription>{copy.providers_desc}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <ProviderBlock
            title={copy.provider_password}
            hint={copy.password_hint}
            enabled={isEnabled(providers, 'password')}
            onEnabledChange={(on) =>
              form.setValue('providers', setProviderEnabled(form.getValues('providers'), 'password', on))
            }
          />

          <ProviderBlock
            title={copy.provider_email}
            hint={copy.email_desc}
            enabled={isEnabled(providers, 'email')}
            onEnabledChange={(on) =>
              form.setValue('providers', setProviderEnabled(form.getValues('providers'), 'email', on))
            }
          >
            <FormField
              control={form.control}
              name="magicLinkDevLog"
              render={({ field }) => (
                <label className="flex items-center justify-between gap-4 rounded-md border border-border/50 bg-background/80 px-3 py-2 text-sm">
                  <span className="text-[13px]">{copy.magic_link_dev_log}</span>
                  <Switch checked={field.value} onCheckedChange={field.onChange} />
                </label>
              )}
            />
            <FormField
              control={form.control}
              name="emailFrom"
              render={({ field }) => (
                <Field id="email-from" label={copy.email_from}>
                  <Input id="email-from" className="h-9" {...field} />
                </Field>
              )}
            />
            <FormField
              control={form.control}
              name="mailTransport"
              render={({ field }) => (
                <Field id="mail-transport" label={copy.mail_transport}>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="mail-transport" className="h-9">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="resend">{copy.transport_resend}</SelectItem>
                      <SelectItem value="smtp">{copy.transport_smtp}</SelectItem>
                    </SelectContent>
                  </Select>
                </Field>
              )}
            />
            {mailTransport === 'resend' ? (
              <FormField
                control={form.control}
                name="resendApiKey"
                render={({ field }) => (
                  <SecretInput id="resend-key" label={copy.resend_api_key} {...field} />
                )}
              />
            ) : (
              <div className="grid gap-4 sm:grid-cols-2">
                <FormField
                  control={form.control}
                  name="smtpHost"
                  render={({ field }) => (
                    <Field id="smtp-host" label={copy.smtp_host} className="sm:col-span-2">
                      <Input id="smtp-host" className="h-9" {...field} />
                    </Field>
                  )}
                />
                <FormField
                  control={form.control}
                  name="smtpPort"
                  render={({ field }) => (
                    <Field id="smtp-port" label={copy.smtp_port}>
                      <Input id="smtp-port" className="h-9" {...field} />
                    </Field>
                  )}
                />
                <FormField
                  control={form.control}
                  name="smtpUsername"
                  render={({ field }) => (
                    <Field id="smtp-user" label={copy.smtp_username}>
                      <Input id="smtp-user" className="h-9" {...field} />
                    </Field>
                  )}
                />
                <div className="sm:col-span-2">
                  <FormField
                    control={form.control}
                    name="smtpPassword"
                    render={({ field }) => (
                      <SecretInput id="smtp-pass" label={copy.smtp_password} {...field} />
                    )}
                  />
                </div>
              </div>
            )}
          </ProviderBlock>

          <ProviderBlock
            title={copy.provider_github}
            enabled={isEnabled(providers, 'github')}
            onEnabledChange={(on) =>
              form.setValue('providers', setProviderEnabled(form.getValues('providers'), 'github', on))
            }
          >
            <FormField
              control={form.control}
              name="githubClientId"
              render={({ field }) => (
                <Field id="gh-id" label={copy.oauth_client_id}>
                  <Input id="gh-id" className="h-9 font-mono text-sm" {...field} />
                </Field>
              )}
            />
            <FormField
              control={form.control}
              name="githubClientSecret"
              render={({ field }) => (
                <SecretInput id="gh-secret" label={copy.oauth_client_secret} {...field} />
              )}
            />
          </ProviderBlock>

          <ProviderBlock
            title={copy.provider_google}
            enabled={isEnabled(providers, 'google')}
            onEnabledChange={(on) =>
              form.setValue('providers', setProviderEnabled(form.getValues('providers'), 'google', on))
            }
          >
            <FormField
              control={form.control}
              name="googleClientId"
              render={({ field }) => (
                <Field id="go-id" label={copy.oauth_client_id}>
                  <Input id="go-id" className="h-9 font-mono text-sm" {...field} />
                </Field>
              )}
            />
            <FormField
              control={form.control}
              name="googleClientSecret"
              render={({ field }) => (
                <SecretInput id="go-secret" label={copy.oauth_client_secret} {...field} />
              )}
            />
          </ProviderBlock>
        </CardContent>
      </Card>

      <div className="sticky bottom-0 z-10 -mx-1 flex items-center justify-end gap-2 border-t border-border/80 bg-background/95 py-4 backdrop-blur supports-[backdrop-filter]:bg-background/85">
        <Button type="submit" disabled={saving} className="min-w-[7rem]">
          {saving ? (
            <>
              <Spinner className="mr-2 size-4" />
              {t.core.common.processing}
            </>
          ) : (
            t.core.common.save
          )}
        </Button>
      </div>
      </form>
    </Form>
  );
}
