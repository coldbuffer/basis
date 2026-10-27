import { BotAvatar } from 'bot-avatars';
import { lazy, Suspense, useEffect, useMemo, useState, type CSSProperties } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';

import { CapabilitiesSection } from '@/components/app/marketing/capabilities-section.js';
import { FaqSection } from '@/components/app/marketing/faq-section.js';
import { HowItWorksSection } from '@/components/app/marketing/how-it-works-section.js';
import { ProductSiteFooter } from '@/components/app/marketing/product-site-footer.js';
import { ProductSiteHeader } from '@/components/app/marketing/product-site-header.js';
import { SelfHostSection } from '@/components/app/marketing/self-host-section.js';
import { UseCasesSection } from '@/components/app/marketing/use-cases-section.js';
import { Button } from '@/components/ui/button.js';
import { i18nIndexedList } from '@/i18n/indexed-list.js';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog.js';
import { useI18n } from '@/i18n/context.js';
import { useTheme } from '@/lib/shell/theme.js';
import { cn } from '@/lib/utils.js';

import {
  AuthFormCard,
  loadAuthProviders,
  type AuthProviders,
} from './auth-form-card.js';

const AstralShell = lazy(() =>
  import('./astral-shell.js').then((mod) => ({ default: mod.AstralShell })),
);

export function LoginScreen() {
  const { t, locale } = useI18n();
  const { theme } = useTheme();
  const m = t.home.marketing;
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [open, setOpen] = useState(() => {
    const mode = searchParams.get('mode');
    return mode === 'register' || mode === 'login';
  });
  const isRegister = searchParams.get('mode') === 'register';
  const isDark = theme === 'dark';
  const [authProviders, setAuthProviders] = useState<AuthProviders | null>(null);
  const canvasBg = isDark ? '#090b10' : '#ffffff';
  const shellProps = useMemo(
    () =>
      isDark
        ? {
            colors: ['#e0a04a', '#f6ead2'] as string[],
            radius: 0.58,
            originX: 0.58,
            originY: 0.42,
            tilt: 24,
            spin: 0.9,
            nodes: 2000,
          }
        : {
            colors: ['#152033', '#d4880a'] as string[],
            radius: 0.6,
            originX: 0.55,
            originY: 0.38,
            tilt: 30,
            spin: 0.85,
            nodes: 2000,
          },
    [isDark],
  );

  useEffect(() => {
    void loadAuthProviders().then(setAuthProviders);
  }, []);

  // The console is viewport-locked; the landing needs document scroll for its sections.
  useEffect(() => {
    const root = document.documentElement;
    root.dataset.marketing = 'true';
    return () => {
      delete root.dataset.marketing;
    };
  }, []);

  useEffect(() => {
    const mode = searchParams.get('mode');
    if (mode === 'register' || mode === 'login') setOpen(true);
  }, [searchParams]);

  useEffect(() => {
    const previous = document.title;
    document.title = m.document_title;
    return () => {
      document.title = previous;
    };
  }, [m.document_title]);

  // React Router updates the hash without scrolling; keep nav anchors usable.
  useEffect(() => {
    if (!location.hash) return;
    const id = decodeURIComponent(location.hash.slice(1));
    const target = document.getElementById(id);
    if (!target) return;
    const frame = requestAnimationFrame(() => {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    return () => cancelAnimationFrame(frame);
  }, [location.hash]);

  const heroTitleSize =
    locale === 'zh'
      ? 'text-[2.5rem] sm:text-[2.75rem] lg:text-[3.4rem]'
      : 'text-[1.65rem] sm:text-4xl lg:text-[2.65rem]';

  function openAuth(mode: 'login' | 'register') {
    setSearchParams({ mode }, { replace: true });
    setOpen(true);
  }

  function onOpenChange(next: boolean) {
    setOpen(next);
    const mode = searchParams.get('mode');
    if (!next && (mode === 'register' || mode === 'login')) {
      setSearchParams({}, { replace: true });
    }
  }

  return (
    <div
      className="relative flex min-h-dvh flex-col bg-background text-foreground"
      style={{
        background: isDark ? '#090b10' : '#ffffff',
        '--login-canvas': isDark ? '#090b10' : '#ffffff',
        '--login-panel': isDark ? '#121820' : '#152033',
        '--login-panel-fg': '#f4f1ea',
        '--login-panel-muted': 'rgb(244 241 234 / 0.68)',
        '--login-panel-faint': isDark ? 'rgb(244 241 234 / 0.4)' : 'rgb(244 241 234 / 0.42)',
        '--login-panel-line': isDark ? 'rgb(244 241 234 / 0.12)' : 'rgb(244 241 234 / 0.14)',
        '--login-gold': isDark ? '#e8a830' : '#e0a04a',
        '--login-cta-bg': isDark ? '#f3ead7' : '#152033',
        '--login-cta-fg': isDark ? '#152033' : '#f6f4ef',
        '--login-cta-shimmer': isDark ? '#e8a830' : '#d4880a',
      } as CSSProperties}
    >
      <a
        href="#product"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-background focus:px-4 focus:py-2 focus:text-sm focus:text-foreground focus:shadow-lg"
      >
        {m.skip_to_content}
      </a>

      <ProductSiteHeader onGetStarted={() => openAuth('register')} />

      <main className="relative -mt-14 flex flex-1 flex-col sm:-mt-16">
        <section
          id="product"
          className="relative flex min-h-dvh flex-col overflow-x-clip"
        >
          <div className="absolute inset-y-0 right-0 z-[1] w-full sm:w-[54%] lg:w-[50%]" aria-hidden>
            <Suspense
              fallback={
                <div className="h-full w-full bg-[radial-gradient(circle_at_60%_40%,var(--login-canvas),transparent_70%)]" />
              }
            >
              <AstralShell
                className="pointer-events-auto h-full min-h-0 w-full"
                backgroundColor={canvasBg}
                {...shellProps}
                interactive
                draggable
                clickPulse
                dpr={1.75}
              />
            </Suspense>
            <div
              className="pointer-events-none absolute inset-0 bg-gradient-to-r from-[var(--login-canvas)] from-35% via-[var(--login-canvas)]/80 to-transparent sm:from-0% sm:via-[var(--login-canvas)]/40"
              aria-hidden
            />
            <div
              className="pointer-events-none absolute inset-x-0 top-0 z-[2] h-16 bg-gradient-to-b from-[var(--login-canvas)] via-[var(--login-canvas)]/45 to-transparent sm:h-24"
              aria-hidden
            />
          </div>

          <div className="pointer-events-none relative z-10 flex min-w-0 flex-1 flex-col overflow-visible px-5 py-4 sm:py-5 sm:pl-8 sm:pr-[54%] lg:pr-[50%]">
            <div className="pointer-events-auto flex min-h-0 min-w-0 flex-1 flex-col items-start justify-center">
              <div className="min-w-0 w-full max-w-2xl">
                <p className="max-w-xl text-xs leading-relaxed text-pretty text-muted-foreground sm:text-[13px]">
                  {m.hero_eyebrow}
                </p>
                <h1
                  className={cn(
                    'mt-5 min-w-0 max-w-full font-semibold leading-[1.1] tracking-[-0.035em] sm:mt-5',
                    heroTitleSize,
                  )}
                  aria-label={`${m.hero_headline} ${m.hero_headline_rest}`}
                >
                  <span className="relative block w-fit max-w-full">
                    {m.hero_headline}
                    <BotAvatar
                      type="drop"
                      state="default"
                      size={64}
                      color={isDark ? '#d4f0c8' : '#5fbf8a'}
                      ink="#111111"
                      shading="fabric"
                      theme={isDark ? 'dark' : 'light'}
                      className="pointer-events-auto absolute -right-3 bottom-full z-20 sm:-right-4"
                    />
                  </span>
                  <span className="mt-1 block text-[var(--login-gold)] sm:mt-2">
                    {m.hero_headline_rest}
                  </span>
                </h1>
              <p className="mt-5 max-w-xl text-[13px] leading-relaxed text-pretty text-muted-foreground sm:mt-6 sm:text-sm">
                {m.hero_subhead}
              </p>
              <div className="mt-5 flex flex-wrap items-center justify-start gap-2.5 sm:mt-6 sm:gap-3">
                <Button
                  type="button"
                  size="default"
                  className="bg-[var(--login-cta-bg)] px-6 text-[var(--login-cta-fg)] hover:bg-[var(--login-cta-bg)] hover:brightness-110 sm:px-7"
                  onClick={() => openAuth('login')}
                  data-analytics="cta_sign_in"
                >
                  {m.cta_login}
                </Button>
                <Button
                  type="button"
                  size="default"
                  variant="ghost"
                  className="border border-foreground/15 bg-transparent px-6 text-foreground hover:bg-foreground/6 sm:px-7"
                  asChild
                >
                  <Link to="/docs/quickstart" data-analytics="cta_read_docs">
                    {m.cta_docs}
                  </Link>
                </Button>
              </div>
              <ul className="mt-6 flex flex-wrap justify-start gap-x-4 gap-y-2 border-t border-border/60 pt-4 text-[11px] leading-relaxed text-muted-foreground sm:mt-7 sm:pt-5 sm:text-xs">
                {i18nIndexedList(m.trust).map((item) => (
                  <li key={item.label}>
                    {'external' in item && item.external ? (
                      <a
                        href={item.to}
                        target="_blank"
                        rel="noreferrer"
                        className="underline-offset-4 hover:text-foreground hover:underline"
                      >
                        {item.label}
                      </a>
                    ) : (
                      <Link
                        to={item.to}
                        className="underline-offset-4 hover:text-foreground hover:underline"
                      >
                        {item.label}
                      </Link>
                    )}
                  </li>
                ))}
              </ul>
              </div>
            </div>
          </div>
        </section>

        <HowItWorksSection />
        <CapabilitiesSection />
        <UseCasesSection />
        <SelfHostSection />
        <FaqSection />
      </main>

      <ProductSiteFooter />

      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="flex max-h-[calc(100%-1rem)] flex-col gap-0 overflow-hidden border-black/10 bg-white p-0 shadow-[0_24px_64px_-20px_rgb(0_0_0_/_0.45)] sm:max-w-[24.5rem] data-[state=closed]:[--tw-exit-scale:1] data-[state=open]:[--tw-enter-scale:1] dark:border-white/10 dark:bg-[#141a22] [&_[data-slot=dialog-close]]:top-3.5 [&_[data-slot=dialog-close]]:right-3.5">
          <DialogTitle className="sr-only">
            {isRegister ? t.login.page.register_title : t.login.page.title}
          </DialogTitle>
          <DialogDescription className="sr-only">
            {isRegister ? t.login.page.register_subtitle : t.login.page.subtitle}
          </DialogDescription>
          <AuthFormCard providers={authProviders} />
        </DialogContent>
      </Dialog>
    </div>
  );
}
