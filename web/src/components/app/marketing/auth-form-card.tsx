import { zodResolver } from '@hookform/resolvers/zod';
import { useEffect, useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { useSearchParams } from 'react-router-dom';
import { z } from 'zod';

import { Button } from '@/components/ui/button.js';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
} from '@/components/ui/form.js';
import { Input } from '@/components/ui/input.js';
import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';
import { useI18n } from '@/i18n/context.js';
import type { Locale } from '@/i18n/locale.js';
import { fmt } from '@/i18n/format.js';
import { formatUserFacingApiError } from '@/lib/errors/api-error-message.js';
import { authV1Path } from '@/lib/openapi/api-v1-path.js';
import { useBasisSession } from '@/lib/session/basis-session.js';
import { publicOpenApiGET, publicOpenApiPOST } from '@/lib/openapi/client.js';
import { cn } from '@/lib/utils.js';

type AuthMode = 'login' | 'register';
type AuthPanel = 'password' | 'magic';

export type AuthProviders = {
  password?: boolean;
  github: boolean;
  google: boolean;
  magic_link: boolean;
  org_oidc?: boolean;
  org_saml?: boolean;
  org_cas?: boolean;
};

type OrgSsoHint = {
  available: boolean;
  org_slug?: string;
  org_name?: string;
  login_url?: string;
  login_path?: string;
  auth_policy?: string;
  password_login_allowed?: boolean;
  protocol?: string;
};

type OrgSsoOption = {
  organization_id: string;
  org_slug: string;
  org_name: string;
  login_url: string;
  login_path: string;
  auth_policy?: string;
  protocol?: string;
};

export async function loadAuthProviders(): Promise<AuthProviders> {
  try {
    return await publicOpenApiGET<AuthProviders>('/api/v1/auth/providers');
  } catch {
    return { github: false, google: false, magic_link: false, org_oidc: true, org_saml: false, org_cas: true };
  }
}

const authFormSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
  displayName: z.string().optional(),
});

type AuthFormValues = z.infer<typeof authFormSchema>;

function authSchemaForMode(mode: AuthMode) {
  return authFormSchema.superRefine((data, ctx) => {
    if (mode === 'register' && !data.displayName?.trim()) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['displayName'],
        message: 'Required',
      });
    }
  });
}

type AuthFormCardProps = {
  providers: AuthProviders | null;
};

export function AuthFormCard({ providers }: AuthFormCardProps) {
  const { t, locale } = useI18n();
  const { login, register } = useBasisSession();
  const [searchParams, setSearchParams] = useSearchParams();
  const mode: AuthMode = searchParams.get('mode') === 'register' ? 'register' : 'login';
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [authPanel, setAuthPanel] = useState<AuthPanel>('password');
  const [magicBusy, setMagicBusy] = useState(false);
  const [magicNotice, setMagicNotice] = useState<string | null>(null);
  const [orgSsoHint, setOrgSsoHint] = useState<OrgSsoHint | null>(null);
  const [orgSsoOptions, setOrgSsoOptions] = useState<OrgSsoOption[]>([]);
  const orgSsoEnabled = Boolean(providers?.org_oidc || providers?.org_saml || providers?.org_cas);
  const resolver = useMemo(() => zodResolver(authSchemaForMode(mode)), [mode]);
  const isRegister = mode === 'register';

  const form = useForm<AuthFormValues>({
    resolver,
    defaultValues: { email: '', password: '', displayName: '' },
  });
  const emailValue = form.watch('email');

  useEffect(() => {
    setAuthPanel('password');
  }, [mode]);

  useEffect(() => {
    if (!orgSsoEnabled || isRegister || authPanel === 'magic') {
      setOrgSsoOptions([]);
      return;
    }
    void publicOpenApiGET<{ options?: OrgSsoOption[] }>('/api/v1/auth/org-sso-options')
      .then((body) => setOrgSsoOptions(body.options ?? []))
      .catch(() => setOrgSsoOptions([]));
  }, [orgSsoEnabled, isRegister, authPanel]);

  useEffect(() => {
    if (!orgSsoEnabled || isRegister || authPanel === 'magic') {
      setOrgSsoHint(null);
      return;
    }
    const trimmed = emailValue.trim();
    if (!trimmed.includes('@')) {
      setOrgSsoHint(null);
      return;
    }
    const timer = window.setTimeout(() => {
      void publicOpenApiGET<OrgSsoHint>(
        `/api/v1/auth/org-sso-hint?email=${encodeURIComponent(trimmed)}`,
      )
        .then((hint) => {
          setOrgSsoHint(hint.available ? hint : null);
        })
        .catch(() => setOrgSsoHint(null));
    }, 400);
    return () => window.clearTimeout(timer);
  }, [emailValue, orgSsoEnabled, isRegister, authPanel]);

  function switchMode(next: AuthMode) {
    setError(null);
    setAuthPanel('password');
    setMagicNotice(null);
    setShowPassword(false);
    form.clearErrors();
    if (next === 'register') {
      setSearchParams({ mode: 'register' }, { replace: true });
    } else {
      setSearchParams({}, { replace: true });
    }
  }

  async function onMagicLink() {
    setError(null);
    setMagicNotice(null);
    const ok = await form.trigger('email');
    if (!ok) return;
    const address = form.getValues('email').trim();
    setMagicBusy(true);
    try {
      await publicOpenApiPOST('/api/v1/auth/magic-link/request', {
        body: { email: address },
      });
      setMagicNotice(t.login.page.magic_link_sent);
    } catch (err) {
      const message = formatUserFacingApiError(err, locale as Locale);
      setError(message || t.login.page.magic_link_failed);
    } finally {
      setMagicBusy(false);
    }
  }

  async function onSubmit(values: AuthFormValues) {
    setError(null);
    setBusy(true);
    try {
      if (mode === 'login') await login(values.email, values.password);
      else await register(values.email, values.password, values.displayName?.trim() ?? '');
    } catch (err) {
      const message = formatUserFacingApiError(err, locale as Locale);
      setError(message || t.login.page.login_failed);
    } finally {
      setBusy(false);
    }
  }

  const isMagicPanel = authPanel === 'magic' && !isRegister;
  const showMagicLink = !isRegister && !isMagicPanel && providers?.magic_link === true;
  const showGithub = !isRegister && providers?.github === true;
  const showGoogle = !isRegister && providers?.google === true;
  const showOrgSso =
    !isMagicPanel && !isRegister && (orgSsoOptions.length > 0 || orgSsoHint?.available === true);
  const showOAuth = !isMagicPanel && (showGithub || showGoogle || showOrgSso);
  const showPasswordLogin = !isMagicPanel && providers?.password !== false;
  const showMagicEntry = showMagicLink;

  function openMagicPanel() {
    setError(null);
    setMagicNotice(null);
    form.clearErrors('password');
    setAuthPanel('magic');
  }

  function backToPasswordPanel() {
    setError(null);
    setMagicNotice(null);
    form.clearErrors();
    setAuthPanel('password');
  }

  const fieldLabel = 'text-[13px] font-medium text-foreground/75';
  const fieldInput =
    'h-10 border-foreground/12 bg-[#f4f5f7] shadow-none dark:border-white/12 dark:bg-[#0c1016]';

  return (
    <div className="flex min-h-0 flex-col">
      <div className="pt-5 pr-12 pb-0 pl-6">
        <h2 className="text-xl font-semibold tracking-[-0.03em] text-foreground">
          {isMagicPanel
            ? t.login.page.magic_link_title
            : isRegister
              ? t.login.page.register_title
              : t.login.page.title}
        </h2>
        <p className="mt-1.5 text-sm leading-snug text-muted-foreground">
          {isMagicPanel
            ? t.login.page.magic_link_subtitle
            : isRegister
              ? t.login.page.register_subtitle
              : t.login.page.subtitle}
        </p>
      </div>

      <Form {...form}>
        <form
          className="mt-4 flex min-h-0 flex-col"
          onSubmit={
            isMagicPanel
              ? (event) => {
                  event.preventDefault();
                  void onMagicLink();
                }
              : form.handleSubmit(onSubmit)
          }
        >
          <div className="min-h-0 space-y-3 overflow-y-auto px-6">
            <div
              className={cn(
                'grid transition-[grid-template-rows] duration-200 ease-out',
                isRegister && !isMagicPanel ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]',
              )}
            >
              <div className="min-h-0 overflow-hidden">
                <FormField
                  control={form.control}
                  name="displayName"
                  render={({ field }) => (
                    <FormItem className="space-y-1.5 pb-3">
                      <FormLabel className={fieldLabel}>{t.login.page.display_name_label}</FormLabel>
                      <FormControl>
                        <Input
                          autoComplete="name"
                          placeholder={t.login.page.display_name_placeholder}
                          className={fieldInput}
                          tabIndex={isRegister ? 0 : -1}
                          aria-hidden={!isRegister}
                          {...field}
                        />
                      </FormControl>
                    </FormItem>
                  )}
                />
              </div>
            </div>
            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem className="space-y-1.5">
                  <FormLabel className={fieldLabel}>{t.login.page.email_label}</FormLabel>
                  <FormControl>
                    <Input
                      type="email"
                      autoComplete="email"
                      placeholder={t.login.page.email_placeholder}
                      className={fieldInput}
                      {...field}
                    />
                  </FormControl>
                </FormItem>
              )}
            />
            <div
              className={cn(
                'grid transition-[grid-template-rows] duration-200 ease-out',
                isMagicPanel || !showPasswordLogin ? 'grid-rows-[0fr]' : 'grid-rows-[1fr]',
              )}
            >
              <div className="min-h-0 overflow-hidden">
                <FormField
                  control={form.control}
                  name="password"
                  render={({ field }) => (
                    <FormItem className="space-y-1.5">
                      <FormLabel className={fieldLabel}>{t.login.page.password_label}</FormLabel>
                      <div className="relative">
                        <FormControl>
                          <Input
                            type={showPassword ? 'text' : 'password'}
                            autoComplete={isRegister ? 'new-password' : 'current-password'}
                            placeholder={t.login.page.password_placeholder}
                            className={`${fieldInput} pr-10`}
                            tabIndex={isMagicPanel ? -1 : 0}
                            aria-hidden={isMagicPanel}
                            {...field}
                          />
                        </FormControl>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon-sm"
                          className="absolute top-1/2 right-1 -translate-y-1/2 text-muted-foreground"
                          aria-label={showPassword ? t.login.page.hide_password : t.login.page.show_password}
                          aria-pressed={showPassword}
                          tabIndex={isMagicPanel ? -1 : 0}
                          onClick={() => setShowPassword((visible) => !visible)}
                        >
                          <PublicIcon name={showPassword ? 'eye-off' : 'eye-open'} size={16} />
                        </Button>
                      </div>
                    </FormItem>
                  )}
                />
              </div>
            </div>
            {error && (
              <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-sm leading-relaxed text-destructive">
                {error}
              </p>
            )}
          </div>
          <div className="px-6 pt-3 space-y-2">
            {isMagicPanel ? (
              <Button
                type="button"
                size="lg"
                disabled={magicBusy}
                className="w-full bg-[#152033] text-[#f6f4ef] hover:bg-[#152033] hover:brightness-110 dark:bg-[#f3ead7] dark:text-[#152033] dark:hover:bg-[#f3ead7]"
                onClick={() => void onMagicLink()}
              >
                {magicBusy ? t.login.page.submitting : t.login.page.magic_link_send}
              </Button>
            ) : showPasswordLogin ? (
              <Button
                type="submit"
                size="lg"
                disabled={busy}
                className="w-full bg-[#152033] text-[#f6f4ef] hover:bg-[#152033] hover:brightness-110 dark:bg-[#f3ead7] dark:text-[#152033] dark:hover:bg-[#f3ead7]"
              >
                {busy ? t.login.page.submitting : isRegister ? t.login.page.register_submit : t.login.page.submit}
              </Button>
            ) : null}
            <div
              className={cn(
                'grid transition-[grid-template-rows] duration-200 ease-out',
                showMagicEntry ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]',
              )}
            >
              <div className="min-h-0 space-y-2 overflow-hidden">
                <p className="text-center text-xs text-muted-foreground">{t.login.page.or}</p>
                <Button
                  type="button"
                  variant="outline"
                  size="lg"
                  className="w-full"
                  onClick={openMagicPanel}
                >
                  {t.login.page.magic_link_entry}
                </Button>
              </div>
            </div>
            {magicNotice ? (
              <p className="text-xs text-muted-foreground">{magicNotice}</p>
            ) : null}
          </div>
        </form>
      </Form>

      <div
        className={cn(
          'grid transition-[grid-template-rows] duration-200 ease-out',
          showOAuth ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]',
        )}
      >
        <div className="min-h-0 overflow-hidden">
          <div className="mx-6 mt-1 space-y-2 pb-2">
          <p className="text-center text-xs text-muted-foreground">{t.login.page.or_continue_with}</p>
          <div className="grid grid-cols-1 gap-2">
            {showOrgSso
              ? (orgSsoOptions.length > 0
                  ? orgSsoOptions
                  : orgSsoHint?.available
                    ? [
                        {
                          org_slug: orgSsoHint.org_slug ?? '',
                          org_name: orgSsoHint.org_name ?? orgSsoHint.org_slug ?? 'Organization',
                          protocol: orgSsoHint.protocol,
                          login_url:
                            orgSsoHint.login_url ??
                            authV1Path(
                              `${orgSsoHint.protocol ?? 'oidc'}/${orgSsoHint.org_slug ?? ''}/start`,
                            ),
                        },
                      ]
                    : []
                ).map((opt) => (
                  <Button
                    key={`${opt.protocol ?? 'sso'}-${opt.org_slug}`}
                    type="button"
                    variant="outline"
                    size="sm"
                    asChild
                    data-testid="login-org-sso"
                  >
                    <a href={opt.login_url}>
                      {fmt(t.login.page.continue_org_sso, {
                        org: opt.org_name || opt.org_slug || 'Organization',
                      })}
                    </a>
                  </Button>
                ))
              : null}
            <div
              className={
                showGithub && showGoogle ? 'grid grid-cols-2 gap-2' : 'grid grid-cols-1 gap-2'
              }
            >
              {showGithub ? (
                <Button type="button" variant="outline" size="sm" asChild>
                  <a href={authV1Path('oauth/github/start')}>{t.login.page.continue_github}</a>
                </Button>
              ) : null}
              {showGoogle ? (
                <Button type="button" variant="outline" size="sm" asChild>
                  <a href={authV1Path('oauth/google/start')}>{t.login.page.continue_google}</a>
                </Button>
              ) : null}
            </div>
          </div>
          </div>
        </div>
      </div>

      <p className="mx-6 mt-3 mb-4 border-t border-foreground/10 pt-3.5 text-sm text-muted-foreground">
        {isMagicPanel ? (
          <Button
            type="button"
            variant="link"
            className="h-auto p-0 font-medium text-foreground"
            onClick={backToPasswordPanel}
          >
            {t.login.page.back_to_password_login}
          </Button>
        ) : (
          <>
            {isRegister ? t.login.page.has_account : t.login.page.no_account}{' '}
            <Button
              type="button"
              variant="link"
              className="h-auto p-0 font-medium text-foreground"
              onClick={() => switchMode(isRegister ? 'login' : 'register')}
            >
              {isRegister ? t.login.page.switch_to_login : t.login.page.switch_to_register}
            </Button>
          </>
        )}
      </p>
    </div>
  );
}
