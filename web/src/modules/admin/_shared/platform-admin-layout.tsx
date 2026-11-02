import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { Spinner } from '@/components/ui/spinner.js';
import { useI18n } from '@/i18n/context.js';
import { useBasisSession } from '@/lib/session/basis-session.js';
import { appAuthRequired, basisIsDesktopProduct } from '@/lib/runtime/basis-runtime.js';
import { visiblePlatformNavItems } from '@/lib/nav/nav-config.js';
import { useSettingsAccess } from '@/lib/shell/use-settings-access.js';

function isDesktopBlockedAdminPath(pathname: string): boolean {
  return (
    pathname === '/admin/users' ||
    pathname.startsWith('/admin/users/') ||
    pathname === '/admin/settings' ||
    pathname.startsWith('/admin/settings/') ||
    pathname === '/admin/audit' ||
    pathname.startsWith('/admin/audit/')
  );
}

export function PlatformAdminLayout() {
  const { t } = useI18n();
  const { ready, user, isAdmin, homePath } = useBasisSession();
  const location = useLocation();
  const canSettings = useSettingsAccess();
  const desktopProduct = basisIsDesktopProduct();
  const authRequired = appAuthRequired();
  const settingsReady =
    isAdmin || canSettings !== null || (desktopProduct && !authRequired);
  const items = visiblePlatformNavItems(isAdmin, canSettings === true, desktopProduct);

  if (!ready || (!user && authRequired)) {
    return (
      <div className="flex flex-1 items-center justify-center gap-2 text-sm text-muted-foreground">
        <Spinner className="size-4" />
        {t.core.common.loading}
      </div>
    );
  }

  if (!settingsReady) {
    return (
      <div className="flex flex-1 items-center justify-center gap-2 text-sm text-muted-foreground">
        <Spinner className="size-4" />
        {t.core.common.loading}
      </div>
    );
  }

  if (desktopProduct && isDesktopBlockedAdminPath(location.pathname)) {
    return <Navigate to={homePath} replace />;
  }

  if (items.length === 0) {
    return <Navigate to={homePath} replace />;
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <Outlet />
    </div>
  );
}
