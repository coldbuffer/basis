import { Link, useLocation } from 'react-router-dom';
import { AppLogo } from '@/components/app/shared/shell/app-logo.js';
import { BasisShellBrandMark } from '@/components/app/shared/shell/basis-shell-brand.js';
import { WorkspaceSwitcher } from '@/components/app/shared/workspace/frame/switcher.js';
import { BasisAccountMenu } from '@/components/app/shared/shell/basis-account-menu.js';
import { SidebarIcon } from '@/components/app/shared/shell/sidebar-icon.js';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarTrigger,
  useSidebar,
} from '@/components/ui/sidebar.js';
import { ScrollShadow } from '@/components/app/shared/primitives/scroll-shadow.js';
import { useI18n } from '@/i18n/context.js';
import { workspaceNavMenuLabel } from '@/lib/nav/workspace-nav-label.js';
import {
  WORKSPACE_NAV_BY_ZONE,
  WORKSPACE_ZONES,
  type SidebarMenuKey,
  type SidebarNavItem,
  type NavItem,
  isPlatformAdminPath,
  workspacePath,
  platformAdminEntryPath,
  platformPathActive,
  visiblePlatformNavItems,
} from '@/lib/nav/nav-config.js';
import { resolveSidebarWorkspaceId } from '@/lib/workspace/active-id.js';
import { useBasisSession } from '@/lib/session/basis-session.js';
import { useWorkspaceCatalog } from '@/lib/workspace/context.js';
import { workspaceNavSegmentEnabled, useWorkspaceCapabilities } from '@/lib/workspace/capabilities.js';
import { appIsDesktopProduct } from '@/lib/runtime/app-runtime.js';
import { basisIsDesktopProduct } from '@/lib/runtime/basis-runtime.js';
import { isMacDesktop } from '@/lib/shell/desktop-bridge.js';
import { cn } from '@/lib/utils.js';
import { useSettingsAccess } from '@/lib/shell/use-settings-access.js';
import { useWorkspaceFailedProcessingCount } from '@/modules/processing/lib/use-failed-processing-count.js';
import { Badge } from '@/components/ui/badge.js';

export function BasisSidebar({ onLogout }: { onLogout: () => void }) {
  const { t } = useI18n();
  const location = useLocation();
  const { isMobile, setOpenMobile, open, toggleSidebar } = useSidebar();
  const { isAdmin } = useBasisSession();
  const canSettings = useSettingsAccess();
  const desktopProduct = basisIsDesktopProduct();
  const isDesktopShell = appIsDesktopProduct();
  const isMac = isDesktopShell && isMacDesktop();
  const desktopNoDrag = isDesktopShell ? '[-webkit-app-region:no-drag]' : '';
  const platformNavReady = isAdmin || canSettings !== null;
  const platformItems = platformNavReady
    ? visiblePlatformNavItems(isAdmin, canSettings === true, desktopProduct)
    : [];
  const isPlatformAdmin = isPlatformAdminPath(location.pathname);
  const { workspaces } = useWorkspaceCatalog();
  const { caps } = useWorkspaceCapabilities();
  const failedProcessingCount = useWorkspaceFailedProcessingCount();
  const navWorkspaceId = resolveSidebarWorkspaceId(location.pathname, workspaces);
  const adminHome =
    platformNavReady
      ? platformAdminEntryPath(isAdmin, canSettings === true, desktopProduct)
      : '/admin/workspaces';
  const consoleGraphHref = workspacePath(navWorkspaceId, 'graph');
  const homeHref = isPlatformAdmin ? adminHome : '/workspaces';
  const macDesktopBrand = isDesktopShell && isMac;
  const fellowStyleBrand = macDesktopBrand;

  function closeMobile() {
    if (isMobile) setOpenMobile(false);
  }

  function isKbActive(segment: string) {
    const prefix = `/workspaces/${navWorkspaceId}/${segment}`;
    if (segment === 'connectors') {
      const path = location.pathname;
      return path === prefix || path.startsWith(`${prefix}/`);
    }
    return location.pathname === prefix || location.pathname.startsWith(`${prefix}/`);
  }

  function renderWorkspaceNavItem(currentKbId: string, item: SidebarNavItem) {
    const active = isKbActive(item.segment);
    const label = workspaceNavMenuLabel(t, item.labelKey as SidebarMenuKey);
    const enabled = workspaceNavSegmentEnabled(item.segment, caps);
    const disabledTooltip =
      caps?.diagnostic === 'graph_runtime_unavailable'
        ? t.core.workspace_nav.capabilities.graph_runtime_unavailable
        : t.core.workspace_nav.capabilities.unavailable;
    return (
      <SidebarMenuItem key={item.segment}>
        {enabled ? (
          <SidebarMenuButton asChild isActive={active} tooltip={label}>
            <Link to={workspacePath(currentKbId, item.segment)} onClick={closeMobile}>
              <SidebarIcon name={item.icon} />
              <span className="min-w-0 flex-1 truncate group-data-[collapsible=icon]:hidden">
                {label}
              </span>
              {item.segment === 'processing' && failedProcessingCount > 0 ? (
                <Badge
                  variant="destructive"
                  className="ml-auto h-5 min-w-5 shrink-0 justify-center px-1.5 text-[10px] tabular-nums group-data-[collapsible=icon]:hidden"
                  data-testid="sidebar-processing-failed-badge"
                >
                  {failedProcessingCount > 99 ? '99+' : failedProcessingCount}
                </Badge>
              ) : null}
            </Link>
          </SidebarMenuButton>
        ) : (
          <SidebarMenuButton
            disabled
            isActive={false}
            tooltip={`${label} — ${disabledTooltip}`}
          >
            <SidebarIcon name={item.icon} />
            <span className="min-w-0 flex-1 truncate opacity-60 group-data-[collapsible=icon]:hidden">
              {label}
            </span>
          </SidebarMenuButton>
        )}
      </SidebarMenuItem>
    );
  }

  function renderPlatformNavItem(item: NavItem) {
    const active = platformPathActive(location.pathname, item.to, item.exact);
    const label = t.core.workspace_nav.platform[item.labelKey];
    return (
      <SidebarMenuItem key={item.to}>
        <SidebarMenuButton asChild isActive={active} tooltip={label}>
          <Link to={item.to} onClick={closeMobile}>
            <SidebarIcon name={item.icon} />
            <span className="min-w-0 flex-1 truncate group-data-[collapsible=icon]:hidden">
              {label}
            </span>
          </Link>
        </SidebarMenuButton>
      </SidebarMenuItem>
    );
  }

  return (
    <Sidebar
      collapsible="icon"
      className={cn(
        'p-0',
        desktopNoDrag,
        isDesktopShell && 'border-r-0',
        isDesktopShell &&
          !isMac &&
          '[&_[data-slot=sidebar-inner]]:rounded-tl-xl [&_[data-slot=sidebar-inner]]:border-t',
      )}
    >
      {(!isDesktopShell || isMac) && (
        <SidebarHeader
          className={cn(
            'relative z-50 py-0',
            fellowStyleBrand ? 'gap-0' : 'gap-2',
            !fellowStyleBrand &&
              'flex-row items-center gap-1 group-data-[collapsible=icon]:flex-col group-data-[collapsible=icon]:items-center group-data-[collapsible=icon]:px-0',
          )}
        >
          {fellowStyleBrand ? (
            <div aria-hidden className="h-5 w-full shrink-0 [-webkit-app-region:drag]" />
          ) : null}
          {open ? (
            <div
              className={cn(
                'flex w-full items-center justify-between gap-2',
                fellowStyleBrand ? 'h-12' : isMac ? 'h-12' : 'h-16',
              )}
            >
              {fellowStyleBrand ? (
                <BasisShellBrandMark
                  className={cn('min-w-0 flex-1 pl-2', '[-webkit-app-region:drag]')}
                />
              ) : (
                <Link
                  to={homeHref}
                  onClick={closeMobile}
                  className="flex min-w-0 flex-1 items-center gap-2 overflow-hidden pl-2 group-data-[collapsible=icon]:size-8 group-data-[collapsible=icon]:flex-none group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0"
                >
                  <BasisShellBrandMark />
                </Link>
              )}
              <SidebarTrigger
                className={cn(
                  'relative z-50 size-8 shrink-0 opacity-70 hover:opacity-100',
                  fellowStyleBrand && '[-webkit-app-region:no-drag]',
                )}
                aria-label={t.core.shell.sidebar.collapse_sidebar}
              />
            </div>
          ) : (
            <button
              type="button"
              className={cn(
                'relative z-50 flex w-full items-center justify-center',
                fellowStyleBrand || isMac ? 'h-12' : 'h-16',
                fellowStyleBrand && '[-webkit-app-region:no-drag]',
              )}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                toggleSidebar();
              }}
              title={t.core.shell.sidebar.brand}
            >
              <AppLogo size={20} className="pointer-events-none" />
            </button>
          )}
        </SidebarHeader>
      )}
      <SidebarContent className="overflow-hidden group-data-[collapsible=icon]:overflow-hidden">
        <ScrollShadow hideScrollBar className="min-h-0 flex-1" fadeColor="var(--sidebar)">
          <SidebarGroup className="group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:items-center">
            <SidebarGroupContent>
              {isPlatformAdmin ? (
                <div className="flex flex-col gap-3.5 group-data-[collapsible=icon]:gap-2">
                  <div className="mb-1 px-0.5 group-data-[collapsible=icon]:flex group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0">
                    <SidebarMenu>
                      <SidebarMenuItem>
                        <SidebarMenuButton asChild tooltip={t.core.shell.sidebar.back_to_workspace_console}>
                          <Link to={consoleGraphHref} onClick={closeMobile}>
                            <SidebarIcon name="arrow-left" />
                            <span className="min-w-0 flex-1 truncate group-data-[collapsible=icon]:hidden">
                              {t.core.shell.sidebar.back_to_workspace_console}
                            </span>
                          </Link>
                        </SidebarMenuButton>
                      </SidebarMenuItem>
                    </SidebarMenu>
                  </div>
                  <div className="flex flex-col gap-0.5">
                    <div
                      className="px-2 pb-0.5 text-[10px] font-semibold uppercase tracking-wider text-sidebar-foreground/50 group-data-[collapsible=icon]:hidden"
                    >
                      {t.core.shell.sidebar.management}
                    </div>
                    <SidebarMenu>
                      {platformItems.map((item) => renderPlatformNavItem(item))}
                    </SidebarMenu>
                  </div>
                </div>
              ) : (
                <>
                  <div
                    className={cn(
                      'mb-3 group-data-[collapsible=icon]:mb-1 group-data-[collapsible=icon]:flex group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0',
                      isDesktopShell ? 'px-2' : 'px-0.5',
                    )}
                  >
                    <WorkspaceSwitcher />
                  </div>
                  <div className="flex flex-col gap-3.5 group-data-[collapsible=icon]:gap-2">
                    {WORKSPACE_ZONES.map((zone, zoneIndex) => {
                      const zoneLabel = t.core.workspace_nav.workspace_zones[zone];
                      const items = WORKSPACE_NAV_BY_ZONE[zone];
                      return (
                        <div key={zone} className="flex flex-col gap-0.5">
                          {zoneIndex > 0 ? (
                            <div className="mx-2 my-1 hidden h-px bg-sidebar-border group-data-[collapsible=icon]:block" />
                          ) : null}
                          <div
                            className="px-2 pb-0.5 text-[10px] font-semibold uppercase tracking-wider text-sidebar-foreground/50 group-data-[collapsible=icon]:hidden"
                          >
                            {zoneLabel}
                          </div>
                          <SidebarMenu>
                            {items.map((item) => renderWorkspaceNavItem(navWorkspaceId, item))}
                          </SidebarMenu>
                        </div>
                      );
                    })}
                  </div>
                </>
              )}
            </SidebarGroupContent>
          </SidebarGroup>
        </ScrollShadow>
      </SidebarContent>
      <SidebarFooter className="group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:items-center">
        <SidebarMenu className="w-full min-w-0">
          <SidebarMenuItem className="min-w-0">
            <BasisAccountMenu
              onLogout={() => {
                closeMobile();
                void onLogout();
              }}
            />
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
