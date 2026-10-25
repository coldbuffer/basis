export type PlatformNavKey = 'workspaces' | 'users' | 'models' | 'connectors' | 'audit' | 'system';

export type NavItem = {
  to: string;
  labelKey: PlatformNavKey;
  icon: string;
  adminOnly?: boolean;
  /** 仅匹配精确路径（用于 /workspaces） */
  exact?: boolean;
};

export const PLATFORM_ADMIN_PREFIX = '/admin';

export const PLATFORM_NAV: NavItem[] = [
  { to: '/admin/workspaces', labelKey: 'workspaces', icon: 'folder-down-01', exact: true },
  { to: '/admin/users', labelKey: 'users', icon: 'users-profiles-01', adminOnly: true },
  { to: '/admin/models', labelKey: 'models', icon: 'atom', adminOnly: true },
  { to: '/admin/connectors', labelKey: 'connectors', icon: 'plug-01', adminOnly: true },
  { to: '/admin/audit', labelKey: 'audit', icon: 'list-dashes-01', adminOnly: true },
  { to: '/admin/settings', labelKey: 'system', icon: 'settings' },
];

export function platformPathActive(pathname: string, to: string, exact?: boolean): boolean {
  if (exact) return pathname === to;
  return pathname === to || pathname.startsWith(`${to}/`);
}

export function isPlatformAdminPath(pathname: string): boolean {
  if (pathname === PLATFORM_ADMIN_PREFIX || pathname.startsWith(`${PLATFORM_ADMIN_PREFIX}/`)) {
    return true;
  }
  return PLATFORM_NAV.some((item) => platformPathActive(pathname, item.to, item.exact));
}

/** Platform section tabs visible to the current user. */
export function visiblePlatformNavItems(
  isAdmin: boolean,
  canSettings: boolean,
  desktopProduct = false,
): NavItem[] {
  return PLATFORM_NAV.filter((item) => {
    if (
      desktopProduct &&
      (item.labelKey === 'users' || item.labelKey === 'audit' || item.labelKey === 'system')
    ) {
      return false;
    }
    if (item.labelKey === 'workspaces') return isAdmin;
    if (item.adminOnly) return isAdmin;
    if (item.labelKey === 'system') return canSettings;
    return false;
  });
}

export function platformAdminEntryPath(
  isAdmin: boolean,
  canSettings: boolean,
  desktopProduct = false,
): string {
  const items = visiblePlatformNavItems(isAdmin, canSettings, desktopProduct);
  return items[0]?.to ?? '/workspaces';
}

/**
 * Workspace sidebar zones:
 * 1. explore — graph, graph diff, search, entity ledger
 * 2. knowledge — sources, BOCP connections (stream sync lives under connectors routes)
 * 3. schema — ontology, vocabulary, statement mappings
 * 4. govern — smart review, change log, lineage (node provenance)
 * 5. system — integration, settings; alerts via account menu only
 */
export type WorkspaceZone = 'explore' | 'knowledge' | 'schema' | 'govern' | 'system';

export const WORKSPACE_ZONES: WorkspaceZone[] = [
  'explore',
  'knowledge',
  'schema',
  'govern',
  'system',
];

export type WorkspaceNavItem = {
  segment: string;
  labelKey: string;
  icon: string;
};

/** Canonical workspace routes (governance console). */
export const WORKSPACE_REVIEW_SEGMENT = 'review' as const;
export const WORKSPACE_LOG_SEGMENT = 'log' as const;

/** Workspace primary navigation grouped by mental model, with unique icons per item. */
export const WORKSPACE_NAV_BY_ZONE = {
  explore: [
    { segment: 'graph', labelKey: 'graph', icon: 'graph' },
    { segment: 'graph-diff', labelKey: 'graphDiff', icon: 'git-diff' },
    { segment: 'search', labelKey: 'search', icon: 'search-01' },
    { segment: 'entities', labelKey: 'entities', icon: 'atom' },
  ],
  knowledge: [
    { segment: 'sources', labelKey: 'sources', icon: 'book-01' },
    { segment: 'processing', labelKey: 'processing', icon: 'sync' },
    { segment: 'connectors', labelKey: 'connectionsSync', icon: 'database' },
  ],
  schema: [
    { segment: 'ontology', labelKey: 'ontology', icon: 'shapes-01' },
    { segment: 'analyze', labelKey: 'analyze', icon: 'code-01' },
    { segment: 'vocabulary', labelKey: 'vocabulary', icon: 'tag' },
    { segment: 'mappings', labelKey: 'mappings', icon: 'arrows-left-right' },
  ],
  govern: [
    { segment: WORKSPACE_REVIEW_SEGMENT, labelKey: 'review', icon: 'check-square-contained' },
    { segment: 'quality', labelKey: 'dataQuality', icon: 'shield-01' },
    { segment: WORKSPACE_LOG_SEGMENT, labelKey: 'activityLog', icon: 'clock-01' },
    { segment: 'lineage', labelKey: 'lineage', icon: 'path' },
  ],
  system: [
    { segment: 'integration', labelKey: 'integration', icon: 'plug-01' },
    { segment: 'settings', labelKey: 'settings', icon: 'settings' },
  ],
} as const satisfies Record<WorkspaceZone, readonly WorkspaceNavItem[]>;

/** Sidebar `labelKey` values — aligned with per-module `*.menu.*` i18n keys. */
export type SidebarNavKey = {
  [Z in WorkspaceZone]: (typeof WORKSPACE_NAV_BY_ZONE)[Z][number]['labelKey'];
}[WorkspaceZone];

export type SidebarMenuKey = SidebarNavKey | 'alerts';

/** Hub tab / legacy route segments (not primary sidebar nav keys). */
export type HubCapabilityNavKey =
  | 'ontologyVersions'
  | 'alignments'
  | 'sparql'
  | 'reasoning';

/** Routable segments and capability switches (includes legacy `processing`). */
export type WorkspaceNavKey = SidebarMenuKey | HubCapabilityNavKey | 'processing' | typeof WORKSPACE_LOG_SEGMENT;

export type SidebarNavItem = WorkspaceNavItem & { labelKey: SidebarMenuKey };

/** Workspace alerts route (account menu only; not in sidebar zones). */
export const ALERTS_NAV_ITEM: SidebarNavItem = {
  segment: 'alerts',
  labelKey: 'alerts',
  icon: 'bell-01',
};

export const SETTINGS_NAV_ITEM: SidebarNavItem = WORKSPACE_NAV_BY_ZONE.system[1];

function buildWorkspaceNav(): SidebarNavItem[] {
  const items: SidebarNavItem[] = [];
  for (const zone of WORKSPACE_ZONES) {
    for (const item of WORKSPACE_NAV_BY_ZONE[zone]) {
      items.push(item as SidebarNavItem);
    }
  }
  items.push(ALERTS_NAV_ITEM);
  return items;
}

export const WORKSPACE_NAV = buildWorkspaceNav();

export function workspacePath(workspaceId: string, segment: string): string {
  return `/workspaces/${workspaceId}/${segment}`;
}

export function workspaceReviewPath(workspaceId: string): string {
  return workspacePath(workspaceId, WORKSPACE_REVIEW_SEGMENT);
}

export function workspaceLogPath(workspaceId: string): string {
  return workspacePath(workspaceId, WORKSPACE_LOG_SEGMENT);
}

export type DataQualityTab = 'overview' | 'structure' | 'scan';

/** Data quality hub (`/quality`) with optional tab and ontology deep-link for SHACL. */
export function workspaceQualityPath(
  workspaceId: string,
  tab: DataQualityTab = 'overview',
  query?: { ontology_uri?: string },
): string {
  const base = workspacePath(workspaceId, 'quality');
  const params = new URLSearchParams();
  if (tab !== 'overview') {
    params.set('tab', tab);
  }
  const ontologyUri = query?.ontology_uri?.trim();
  if (ontologyUri) {
    params.set('ontology_uri', ontologyUri);
  }
  const q = params.toString();
  return q ? `${base}?${q}` : base;
}

/** BOCP workspace sub-panels (sidebar routes under `/connectors/…`). Home is `/connectors`. */
export type ConnectorPanel = 'mappings' | 'policy' | 'runs';

export function workspaceConnectorHomePath(workspaceId: string): string {
  return workspacePath(workspaceId, 'connectors');
}

export function workspaceConnectorPanelPath(workspaceId: string, panel: ConnectorPanel): string {
  return workspacePath(workspaceId, `connectors/${panel}`);
}

/** Deep-link to OWL versions workspace + proposal review modal (F-ONT-05). */
export function workspaceOntologyProposalPath(workspaceId: string, proposalId: string): string {
  const params = new URLSearchParams({
    tab: 'versions',
    ontologyProposal: proposalId,
  });
  return `${workspacePath(workspaceId, 'ontology')}?${params.toString()}`;
}

/** OWL ontology versions & proposals (separate from ledger review queue). */
export function workspaceOntologyVersionsPath(workspaceId: string): string {
  return `${workspacePath(workspaceId, 'ontology')}?tab=versions`;
}

/** Graph projection diff between two ISO instants (F-DIFF-01). */
export function workspaceGraphDiffPath(workspaceId: string, from?: string, to?: string): string {
  const base = workspacePath(workspaceId, 'graph-diff');
  if (!from && !to) return base;
  const params = new URLSearchParams();
  if (from) params.set('from', from);
  if (to) params.set('to', to);
  const q = params.toString();
  return q ? `${base}?${q}` : base;
}

export function parseWorkspaceIdFromPath(pathname: string): string | null {
  const match = /^\/workspaces\/([^/]+)(?:\/|$)/.exec(pathname);
  if (!match) return null;
  const id = match[1];
  if (!id || id === 'undefined') return null;
  return id as string;
}

/** Sidebar glyph for the page the pathname opens. */
export function menuIconForPath(pathname: string): string | undefined {
  const segment = /^\/workspaces\/[^/]+\/([^/]+)/.exec(pathname)?.[1];
  if (segment) {
    if (segment === 'connectors') {
      return WORKSPACE_NAV.find((item) => item.segment === 'connectors')?.icon;
    }
    return WORKSPACE_NAV.find((item) => item.segment === segment)?.icon;
  }
  return PLATFORM_NAV.find((item) =>
    item.exact ? pathname === item.to : pathname === item.to || pathname.startsWith(`${item.to}/`),
  )?.icon;
}

export function isWorkspaceScopedPath(pathname: string): boolean {
  const id = parseWorkspaceIdFromPath(pathname);
  if (!id) return false;
  const rest = pathname.slice(`/workspaces/${id}`.length);
  if (!rest || rest === '/') return false;
  const segment = rest.replace(/^\//, '').split('/')[0];
  if (segment === 'connectors') {
    return true;
  }
  return WORKSPACE_NAV.some((item) => item.segment === segment);
}
