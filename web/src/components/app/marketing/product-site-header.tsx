import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { ProductMobileNavMenu } from '@/components/app/marketing/product-mobile-nav-menu.js';
import { ProductSiteNav } from '@/components/app/marketing/product-site-nav.js';
import { AppLogo } from '@/components/app/shared/shell/app-logo.js';
import { Button } from '@/components/ui/button.js';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu.js';
import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';
import { useI18n } from '@/i18n/context.js';
import { LocaleMenuItems } from '@/i18n/locale-menu.js';
import { useBasisSession } from '@/lib/session/basis-session.js';
import type { ProductNavKey } from '@/lib/marketing/product-nav.js';
import { cn } from '@/lib/utils.js';
import { useTheme } from '@/lib/shell/theme.js';

type ProductSiteHeaderProps = {
  activeKey?: ProductNavKey;
  /** Home hero: open auth dialog instead of navigating. */
  onGetStarted?: () => void;
};

export function ProductSiteHeader({ activeKey, onGetStarted }: ProductSiteHeaderProps) {
  const { t } = useI18n();
  const { theme, toggleTheme } = useTheme();
  const { ready, user, homePath } = useBasisSession();
  const m = t.home.marketing;
  const isDark = theme === 'dark';
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const getStartedControl =
    onGetStarted != null ? (
      <Button
        type="button"
        size="sm"
        className="rounded-full bg-[var(--login-cta-bg,#152033)] px-4 text-[var(--login-cta-fg,#f6f4ef)] hover:brightness-110"
        onClick={onGetStarted}
        data-analytics="cta_get_started"
      >
        {m.cta_get_started}
      </Button>
    ) : (
      <Button
        type="button"
        size="sm"
        className="rounded-full bg-[var(--login-cta-bg,#152033)] px-4 text-[var(--login-cta-fg,#f6f4ef)] hover:brightness-110"
        asChild
      >
        <Link to="/?mode=register" data-analytics="cta_get_started">
          {m.cta_get_started}
        </Link>
      </Button>
    );

  return (
    <header
      className={cn(
        'sticky top-0 z-30 w-full transition-[border-color,background-color,backdrop-filter] duration-200',
        scrolled && 'border-b border-border/60 bg-background/40 backdrop-blur-lg',
      )}
    >
      <div className="flex h-14 w-full items-center gap-3 px-5 sm:h-16 sm:px-8">
        <Link to="/" className="inline-flex shrink-0 items-center gap-2.5 text-foreground no-underline">
          <AppLogo size={28} label={m.brand} />
          <span className="font-display text-base font-semibold tracking-tight">{m.brand}</span>
        </Link>

        <div className="ml-auto flex items-center gap-2 sm:gap-3">
          <div className="hidden items-center gap-2 lg:flex lg:gap-3">
            <ProductSiteNav activeKey={activeKey} />
            {!(ready && user) ? <div className="shrink-0">{getStartedControl}</div> : null}
          </div>

          {ready && user ? (
            <Button type="button" variant="ghost" size="sm" className="hidden md:inline-flex" asChild>
              <Link to={homePath}>{m.open_console}</Link>
            </Button>
          ) : null}

          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={toggleTheme}
            aria-label={isDark ? m.a11y_theme_light : m.a11y_theme_dark}
            className="text-muted-foreground hover:text-foreground"
          >
            <PublicIcon name={isDark ? 'sun-01' : 'moon-01'} size={18} />
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label={t.core.shell.sidebar.language}
                className="text-muted-foreground hover:text-foreground"
              >
                <PublicIcon name="globe-02" size={18} />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <LocaleMenuItems />
            </DropdownMenuContent>
          </DropdownMenu>

          <ProductMobileNavMenu onGetStarted={onGetStarted} />
        </div>
      </div>
    </header>
  );
}
