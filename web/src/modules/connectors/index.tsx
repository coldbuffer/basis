import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import {
  ConsolePageLayout,
  DataPanel,
  DataPanelBody,
  DataPanelHeader,
} from '@/components/app/shared/console/index.js';
import { JsonEditor } from '@/components/app/shared/primitives/json-editor.js';
import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';
import { Badge } from '@/components/ui/badge.js';
import { Spinner } from '@/components/ui/spinner.js';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog.js';
import { Button } from '@/components/ui/button.js';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog.js';
import { Input } from '@/components/ui/input.js';
import { Label } from '@/components/ui/label.js';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select.js';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs.js';
import { useI18n } from '@/i18n/context.js';
import { fmt, formatLocaleDateTime } from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import { formatUserFacingApiError } from '@/lib/errors/api-error-message.js';
import { ConnectorConnectAuthFields } from '@/modules/connectors/components/connector-connect-auth-fields.js';
import { ConnectorMappingCreateDialog } from '@/modules/connectors/components/connector-mapping-create-dialog.js';
import {
  workspaceConnectorMappingEditPath,
  workspaceConnectorMappingNewPath,
  connectionStorageKey,
  mergeAuthorizationsForList,
  workspaceConnectionsByService,
  workspaceSharedServiceNames,
  type StoredConnection,
} from '@/modules/connectors/lib/connector-connections.js';
import { writeEndUserSubjectId } from '@/modules/connectors/lib/end-user-subject.js';
import { workspaceConnectorsAuthorizationHref } from '@/modules/connectors/lib/playground-deep-link.js';
import {
  catalogProviderNeedsCredentials,
  catalogProviderSupportsOAuth,
  catalogProviderUsesOAuthUserAuthorization,
} from '@/modules/connectors/lib/workspace-app-actions.js';
import { useWorkspaceCatalog } from '@/lib/workspace/context.js';
import {
  type ConnectorPanel,
  workspaceConnectorHomePath,
  workspaceConnectorPanelPath,
  workspacePath,
} from '@/lib/nav/nav-config.js';
import {
  workspaceOpenApiDELETE,
  workspaceOpenApiGET,
  workspaceOpenApiPOST,
  workspaceOpenApiPUT,
} from '@/lib/openapi/client.js';
import { resourceCardSurfaceClass } from '@/lib/ui-classes/card-surface.js';
import {
  connectorAuthNeedsPkce,
  generateOAuthState,
  generatePkcePair,
  workspaceConnectorOAuthRedirectUri,
  savePendingConnectorOAuth,
} from '@/modules/connectors/lib/connector-oauth.js';
import { cn } from '@/lib/utils.js';
import {
  authModeDisplayLabel,
  connectorAuthCatalogEntries,
  findAuthCatalogEntry,
} from '@/modules/connectors/lib/connector-auth-display.js';
import {
  authCredentialFieldsAreBlank,
  authFieldDefaultValues,
  authFieldValuesFromObject,
  buildObjectFromAuthFields,
  hasStructuredAuthForm,
  isOAuth2ConnectManifestOnly,
  parsedCredentialJsonIsBlank,
  type ConnectorAuthCatalogEntry,
} from '@/modules/connectors/lib/connector-auth-fields.js';
import {
  authModesForConnector,
  defaultConnectorConfigForAuth,
  defaultConnectorCredentialsForAuth,
  formatConnectorConnectJson,
} from '@/modules/connectors/lib/connector-connect-defaults.js';

type CatalogConnector = {
  service: string;
  display_name: string;
  description?: string;
  categories?: string[];
  auth?: ConnectorAuthCatalogEntry[];
  streams?: Array<{ name: string; display_name: string }>;
  tools?: Array<{ id: string; name: string }>;
};

type TableMappingDto = {
  id: string;
  source_id: string;
  provider?: string;
    stream_name: string;
  external_table: string;
  primary_key_column: string;
  cursor_column?: string | null;
  label_column: string;
  target_class_uri: string;
  sync_direction: string;
  writeback_mode: string;
  updated_at: string;
};

type OutboxItemDto = {
  id: string;
  entity_id: string;
  status: string;
  created_at: string;
  patch: {
    provider?: string;
    external_table?: string;
    external_pk?: string;
    changes?: Record<string, { old?: unknown; new?: unknown }>;
  };
};

type ConnectorRunDto = {
  id: string;
  service: string;
  operation_kind: string;
  target_id: string;
    started_at: string;
  ok: boolean;
};

const CONNECTOR_PANELS: ConnectorPanel[] = ['mappings', 'policy', 'runs'];

function parseConnectorPanel(raw: string | undefined): ConnectorPanel | null {
  if (raw && (CONNECTOR_PANELS as readonly string[]).includes(raw)) {
    return raw as ConnectorPanel;
  }
  return null;
}

type CatalogSection = 'connectors' | 'authorization';

function parseCatalogSection(raw: string | null): CatalogSection {
  if (raw === 'authorization') {
    return 'authorization';
  }
  return 'connectors';
}

function preferredOAuthAuthMode(
  auth?: ConnectorAuthCatalogEntry[],
): string | undefined {
  const modes = authModesForConnector(auth);
  return modes.find((mode) => mode === 'oauth2') ?? modes.find((mode) => mode === 'oauth2_cc');
}

/** Lock auth mode on Authorization tab when OAuth app is set or provider is OAuth-only. */
function isAuthorizationAuthModeLocked(
  inAuthorizationSection: boolean,
  connector: CatalogConnector | null,
  editing: StoredConnection | null,
  oauthAppConfigured: boolean,
): boolean {
  if (!inAuthorizationSection || !connector) {
    return false;
  }
  if (editing) {
    if (editing.auth_type !== 'oauth2' && editing.auth_type !== 'oauth2_cc') {
      return false;
    }
  } else if (
    !catalogProviderUsesOAuthUserAuthorization(connector) &&
    !oauthAppConfigured
  ) {
    return false;
  }
  return (
    catalogProviderUsesOAuthUserAuthorization(connector) ||
    catalogProviderSupportsOAuth(connector)
  );
}

export function ConnectorsPage() {
  const { id: workspaceId, panel: panelParam } = useParams<{ id: string; panel?: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { t, locale } = useI18n();
  const c = t.connectors.page;
  const { getWorkspace } = useWorkspaceCatalog();

  const panel = parseConnectorPanel(panelParam);
  if (panelParam && !panel) {
    return workspaceId ? <Navigate to={workspaceConnectorHomePath(workspaceId)} replace /> : null;
  }

  const catalogSection = parseCatalogSection(searchParams.get('section'));
  const [searchQuery, setSearchQuery] = useState('');
  const [connectors, setConnectors] = useState<CatalogConnector[]>([]);
  const [catalogConnectors, setCatalogConnectors] = useState<CatalogConnector[]>([]);
  const [workspaceApps, setWorkspaceApps] = useState<CatalogConnector[]>([]);
  const [connections, setConnections] = useState<StoredConnection[]>([]);
  const [appActionService, setAppActionService] = useState<string | null>(null);
  const [disabledAppServices, setDisabledAppServices] = useState<Set<string>>(() => new Set());
  const [addAppDialogOpen, setAddAppDialogOpen] = useState(false);
  const [addAppSearchQuery, setAddAppSearchQuery] = useState('');
  const [connectionsLoading, setConnectionsLoading] = useState(true);
  const [mappings, setMappings] = useState<TableMappingDto[]>([]);
  const [outboxItems, setOutboxItems] = useState<OutboxItemDto[]>([]);
  const [runs, setRuns] = useState<ConnectorRunDto[]>([]);

  const [allowedProvidersInput, setAllowedProvidersInput] = useState('*');
  const [platformAllowedDisplay, setPlatformAllowedDisplay] = useState('*');
  const [effectiveAllowedDisplay, setEffectiveAllowedDisplay] = useState('*');
  const [actionPolicyInput, setActionPolicyInput] = useState('{}');

  function formatAllowlistDisplay(value: string[] | string | undefined): string {
    if (!value || value === '*') return '*';
    if (Array.isArray(value)) return value.join(', ');
    return String(value);
  }

  // Connect dialog state
  const [selectedConnector, setSelectedConnector] = useState<CatalogConnector | null>(null);
  const [connAuthMode, setConnAuthMode] = useState('database_dsn');
  const [connConfigJson, setConnConfigJson] = useState(
    '{\n  "host": "localhost",\n  "port": 5432,\n  "database": "erp"\n}',
  );
  const [connCredsJson, setConnCredsJson] = useState(
    '{\n  "username": "postgres",\n  "password": ""\n}',
  );
  const [connConfigFieldValues, setConnConfigFieldValues] = useState<Record<string, string>>(
    {},
  );
  const [connCredFieldValues, setConnCredFieldValues] = useState<Record<string, string>>({});
  const [connectFormUseJson, setConnectFormUseJson] = useState(false);
  const [oauthClientId, setOauthClientId] = useState('');
  const [oauthClientSecret, setOauthClientSecret] = useState('');
  const [oauthHasSavedSecret, setOauthHasSavedSecret] = useState(false);
  const [oauthAuthorizeUrl, setOauthAuthorizeUrl] = useState<string | null>(null);
  const [editingConnection, setEditingConnection] = useState<StoredConnection | null>(null);
  const [oauthAppTarget, setOauthAppTarget] = useState<CatalogConnector | null>(null);
  const [savingConn, setSavingConn] = useState(false);
  const [savingOAuthApp, setSavingOAuthApp] = useState(false);
  const [checkingKey, setCheckingKey] = useState<string | null>(null);
  const [reauthorizingKey, setReauthorizingKey] = useState<string | null>(null);
  const [buildingOAuthUrl, setBuildingOAuthUrl] = useState(false);
  const [oauthConfigLoadingFor, setOauthConfigLoadingFor] = useState<string | null>(null);
  const [oauthUrlBuildAttempted, setOauthUrlBuildAttempted] = useState(false);

  // Tool runner state
  const [toolService, setToolService] = useState('github');
  const [toolId, setToolId] = useState('list_repositories');
  const [toolArgsJson, setToolArgsJson] = useState('{\n  "per_page": 10\n}');
  const [runningTool, setRunningTool] = useState(false);
  const [toolResultJson, setToolResultJson] = useState<string | null>(null);

  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [deleteMappingId, setDeleteMappingId] = useState<string | null>(null);
  const [deletingMappingId, setDeletingMappingId] = useState<string | null>(null);
  const [createMappingOpen, setCreateMappingOpen] = useState(false);
  const [createMappingInitialTab, setCreateMappingInitialTab] = useState<'auto' | 'manual'>('auto');

  const [addAuthOpen, setAddAuthOpen] = useState(false);
  const [addAuthScope, setAddAuthScope] = useState<'workspace' | 'end_user'>('workspace');
  const [addAuthSubject, setAddAuthSubject] = useState('');
  const [addAuthSearch, setAddAuthSearch] = useState('');
  const [pendingConnectScope, setPendingConnectScope] = useState<'workspace' | 'end_user'>('workspace');
  const [pendingConnectSubjectId, setPendingConnectSubjectId] = useState('');
  const authServiceDeepLinkHandled = useRef(false);

  const installedAppServices = useMemo(
    () => new Set(workspaceApps.map((item) => item.service)),
    [workspaceApps],
  );

  const installableCatalogConnectors = useMemo(() => {
    const q = addAppSearchQuery.trim().toLowerCase();
    return catalogConnectors.filter((item) => {
      if (installedAppServices.has(item.service)) {
        return false;
      }
      if (!q) {
        return true;
      }
      const name = (item.display_name ?? item.service).toLowerCase();
      return name.includes(q) || item.service.toLowerCase().includes(q);
    });
  }, [catalogConnectors, installedAppServices, addAppSearchQuery]);

  const filteredWorkspaceApps = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) {
      return workspaceApps;
    }
    return workspaceApps.filter((item) => {
      const name = (item.display_name ?? item.service).toLowerCase();
      return name.includes(q) || item.service.toLowerCase().includes(q);
    });
  }, [workspaceApps, searchQuery]);

  function setCatalogSection(section: CatalogSection) {
    const next = new URLSearchParams(searchParams);
    next.set('section', section);
    setSearchParams(next, { replace: true });
  }
  const configuredByService = useMemo(
    () => workspaceConnectionsByService(connections),
    [connections],
  );
  const authorizationConnections = useMemo(
    () => mergeAuthorizationsForList(connections),
    [connections],
  );

  const workspaceSharedServices = useMemo(
    () => workspaceSharedServiceNames(connections),
    [connections],
  );

  const addAuthProviders = useMemo(() => {
    const q = addAuthSearch.trim().toLowerCase();
    return workspaceApps.filter((item) => {
      if (addAuthScope === 'end_user' && workspaceSharedServices.has(item.service)) {
        return false;
      }
      if (!q) {
        return true;
      }
      const name = (item.display_name ?? item.service).toLowerCase();
      return name.includes(q) || item.service.toLowerCase().includes(q);
    });
  }, [workspaceApps, addAuthSearch, addAuthScope, workspaceSharedServices]);

  const loadCatalogAndConnections = useCallback(async () => {
    if (!workspaceId) return;
    setConnectionsLoading(true);
    try {
      const [catRes, connRes, polRes] = await Promise.all([
        workspaceOpenApiGET<{
          stats: { providers: number; providers_with_streams: number };
          connectors: CatalogConnector[];
          browse_connectors?: CatalogConnector[];
          workspace_apps?: CatalogConnector[];
        }>(workspaceId, 'connectors/catalog', {
          params: {
            query: {
              limit: 200,
            },
          },
        }),
        workspaceOpenApiGET<{ connections: StoredConnection[] }>(workspaceId, 'connectors/connections'),
        workspaceOpenApiGET<{
          disabled_providers?: string[];
        }>(workspaceId, 'connectors/policy'),
      ]);
      const catalog = catRes.connectors ?? catRes.browse_connectors ?? [];
      const apps = catRes.workspace_apps ?? [];
      setCatalogConnectors(catalog);
      setWorkspaceApps(apps);
      setConnectors(catalog);
      setConnections(connRes.connections ?? []);
      setDisabledAppServices(new Set(polRes.disabled_providers ?? []));
    } catch (err) {
      toast.error(formatUserFacingApiError(err, locale as Locale));
    } finally {
      setConnectionsLoading(false);
    }
  }, [workspaceId, locale]);

  const loadMappings = useCallback(async () => {
    if (!workspaceId) return;
    try {
      const res = await workspaceOpenApiGET<{ mappings: TableMappingDto[] }>(
        workspaceId,
        'connectors/table-mappings',
      );
      setMappings(res.mappings ?? []);
    } catch (err) {
      toast.error(formatUserFacingApiError(err, locale as Locale));
    }
  }, [workspaceId, locale]);

  const loadPolicyAndOutbox = useCallback(async () => {
    if (!workspaceId) return;
    try {
      const [polRes, outRes] = await Promise.all([
        workspaceOpenApiGET<{
          platform_allowed_providers: string[] | string;
          allowed_providers: string[] | string;
          effective_allowed_providers: string[] | string;
          action_policy: Record<string, unknown>;
        }>(workspaceId, 'connectors/policy'),
        workspaceOpenApiGET<{ items: OutboxItemDto[] }>(workspaceId, 'connectors/outbox'),
      ]);
      const ap = polRes.allowed_providers;
      setAllowedProvidersInput(formatAllowlistDisplay(ap));
      setPlatformAllowedDisplay(formatAllowlistDisplay(polRes.platform_allowed_providers));
      setEffectiveAllowedDisplay(formatAllowlistDisplay(polRes.effective_allowed_providers));
      setActionPolicyInput(JSON.stringify(polRes.action_policy ?? {}, null, 2));
      setOutboxItems(outRes.items ?? []);
    } catch (err) {
      toast.error(formatUserFacingApiError(err, locale as Locale));
    }
  }, [workspaceId, locale]);

  const loadRuns = useCallback(async () => {
    if (!workspaceId) return;
    try {
      const res = await workspaceOpenApiGET<{ runs: ConnectorRunDto[] }>(workspaceId, 'connectors/runs');
      setRuns(res.runs ?? []);
    } catch (err) {
      toast.error(formatUserFacingApiError(err, locale as Locale));
    }
  }, [workspaceId, locale]);

  useEffect(() => {
    if (!workspaceId) {
      return;
    }
    const fromUrl = searchParams.get('subject_id')?.trim();
    if (fromUrl) {
      writeEndUserSubjectId(workspaceId, fromUrl);
    }
  }, [workspaceId, searchParams]);

  useEffect(() => {
    if (!workspaceId || panel || catalogSection !== 'authorization') {
      return;
    }
    if (authServiceDeepLinkHandled.current || connectionsLoading) {
      return;
    }
    const service = searchParams.get('service')?.trim();
    if (!service) {
      return;
    }
    const item =
      workspaceApps.find((entry) => entry.service === service) ??
      connectors.find((entry) => entry.service === service);
    if (!item) {
      return;
    }
    const subject = searchParams.get('subject_id')?.trim();
    if (subject && workspaceSharedServices.has(service)) {
      authServiceDeepLinkHandled.current = true;
      toast.error(c.catalog.workspace_shared_blocks_end_user);
      return;
    }
    authServiceDeepLinkHandled.current = true;
    const modes = authModesForConnector(item.auth);
    const preferred = modes[0];
    setEditingConnection(null);
    if (subject) {
      setPendingConnectScope('end_user');
      setPendingConnectSubjectId(subject);
    } else {
      setPendingConnectScope('workspace');
      setPendingConnectSubjectId('');
    }
    setSelectedConnector(item);
    setConnAuthMode(preferred);
    setOauthAuthorizeUrl(null);
    resetOAuthClientFields();
    applyConnectFormForAuth(item, preferred);
    void loadOAuthConfigForService(item.service);
  }, [
    workspaceId,
    panel,
    catalogSection,
    connectionsLoading,
    searchParams,
    workspaceApps,
    connectors,
    workspaceSharedServices,
    c.catalog.workspace_shared_blocks_end_user,
  ]);

  useEffect(() => {
    void loadCatalogAndConnections();
  }, [loadCatalogAndConnections]);

  useEffect(() => {
    if (panel === 'mappings') void loadMappings();
    if (panel === 'policy') void loadPolicyAndOutbox();
    if (panel === 'runs') void loadRuns();
  }, [panel, loadMappings, loadPolicyAndOutbox, loadRuns]);

  useEffect(() => {
    if (panel !== 'mappings' || searchParams.get('suggest') !== '1') {
      return;
    }
    setCreateMappingInitialTab('auto');
    setCreateMappingOpen(true);
    const next = new URLSearchParams(searchParams);
    next.delete('suggest');
    setSearchParams(next, { replace: true });
  }, [panel, searchParams, setSearchParams]);

  function openCreateMapping(tab: 'auto' | 'manual' = 'auto') {
    setCreateMappingInitialTab(tab);
    setCreateMappingOpen(true);
  }

  function goToNewMapping(prefill?: StoredConnection) {
    if (!workspaceId) return;
    navigate(
      workspaceConnectorMappingNewPath(workspaceId, {
        service: prefill?.service,
              }),
    );
  }

  function resetOAuthClientFields() {
    setOauthClientId('');
    setOauthClientSecret('');
    setOauthHasSavedSecret(false);
  }

  function applyConnectFormForAuth(item: CatalogConnector, authMode: string) {
    const entry = findAuthCatalogEntry(item.auth, authMode);
    setConnectFormUseJson(false);
    if (hasStructuredAuthForm(entry)) {
      setConnConfigFieldValues(authFieldDefaultValues(entry?.connection_config));
      setConnCredFieldValues(authFieldDefaultValues(entry?.credentials));
      setConnConfigJson(
        formatConnectorConnectJson(
          buildObjectFromAuthFields(entry?.connection_config, authFieldDefaultValues(entry?.connection_config)),
        ),
      );
      setConnCredsJson(
        formatConnectorConnectJson(
          buildObjectFromAuthFields(entry?.credentials, authFieldDefaultValues(entry?.credentials)),
        ),
      );
    } else {
      setConnConfigFieldValues({});
      setConnCredFieldValues({});
      setConnConfigJson(
        formatConnectorConnectJson(defaultConnectorConfigForAuth(item.service, authMode)),
      );
      setConnCredsJson(
        formatConnectorConnectJson(defaultConnectorCredentialsForAuth(item.service, authMode)),
      );
    }
  }

  function applyConnectFormFromConnection(
    item: CatalogConnector,
    authMode: string,
    existing: StoredConnection,
  ) {
    const entry = findAuthCatalogEntry(item.auth, authMode);
    const cfg = existing.connection_config ?? {};
    setConnectFormUseJson(false);
    if (hasStructuredAuthForm(entry)) {
      setConnConfigFieldValues(authFieldValuesFromObject(entry?.connection_config, cfg));
      setConnCredFieldValues(authFieldDefaultValues(entry?.credentials));
      setConnConfigJson(
        formatConnectorConnectJson(
          buildObjectFromAuthFields(
            entry?.connection_config,
            authFieldValuesFromObject(entry?.connection_config, cfg),
          ),
        ),
      );
      setConnCredsJson(formatConnectorConnectJson({}));
    } else {
      setConnConfigFieldValues({});
      setConnCredFieldValues({});
      setConnConfigJson(formatConnectorConnectJson(cfg));
      setConnCredsJson(formatConnectorConnectJson({}));
    }
  }

  async function loadOAuthConfigForService(
    service: string,
  ): Promise<{ clientId: string; hasSavedSecret: boolean }> {
    if (!workspaceId) {
      return { clientId: '', hasSavedSecret: false };
    }
    setOauthConfigLoadingFor(service);
    resetOAuthClientFields();
    let clientId = '';
    let hasSavedSecret = false;
    try {
      const res = await workspaceOpenApiGET<{
        oauth_config: {
          client_id?: string;
          has_client_secret?: boolean;
        };
      }>(workspaceId, `connectors/oauth-configs/${service}`);
      clientId = res.oauth_config?.client_id?.trim() ?? '';
      hasSavedSecret = Boolean(res.oauth_config?.has_client_secret);
      if (clientId) {
        setOauthClientId(clientId);
      }
      setOauthHasSavedSecret(hasSavedSecret);
    } catch (err) {
      const status = (err as Error & { status?: number }).status;
      if (status === 405 || status === 404) {
        return { clientId, hasSavedSecret };
      }
      toast.error(formatUserFacingApiError(err, locale as Locale));
      return { clientId, hasSavedSecret };
    } finally {
      setOauthConfigLoadingFor((current) => (current === service ? null : current));
    }
    return { clientId, hasSavedSecret };
  }

  function closeConnectDialog() {
    setSelectedConnector(null);
    setEditingConnection(null);
    setOauthAuthorizeUrl(null);
    setOauthUrlBuildAttempted(false);
    setPendingConnectScope('workspace');
    setPendingConnectSubjectId('');
    resetOAuthClientFields();
  }

  function resolveConnectScope(): 'workspace' | 'end_user' {
    if (editingConnection?.connection_scope === 'end_user') {
      return 'end_user';
    }
    if (pendingConnectScope === 'end_user') {
      return 'end_user';
    }
    return 'workspace';
  }

  function resolveConnectSubjectId(): string {
    if (editingConnection?.connection_scope === 'end_user') {
      return (editingConnection.subject_id ?? '').trim();
    }
    if (pendingConnectScope === 'end_user') {
      return pendingConnectSubjectId.trim();
    }
    return '';
  }

  function openAddAuthorizationDialog() {
    setAddAuthScope('workspace');
    setAddAuthSubject('');
    setAddAuthSearch('');
    setAddAuthOpen(true);
  }

  function serviceBlocksEndUserAuthorization(service: string): boolean {
    return workspaceSharedServices.has(service);
  }

  function confirmAddAuthorization(item: CatalogConnector) {
    const scope = addAuthScope;
    const subjectId = addAuthSubject.trim();
    if (scope === 'end_user' && serviceBlocksEndUserAuthorization(item.service)) {
      toast.error(c.catalog.workspace_shared_blocks_end_user);
      return;
    }
    if (scope === 'end_user' && !subjectId) {
      toast.error(c.catalog.subject_id_required);
      return;
    }
    setAddAuthOpen(false);
    if (scope === 'end_user') {
      writeEndUserSubjectId(workspaceId!, subjectId);
    }
    const modes = authModesForConnector(item.auth);
    const preferred = modes.find((m) => m === 'oauth2' || m === 'oauth2_cc') ?? modes[0];
    beginConnectorConnect(item, preferred, {
      scope,
      subjectId: scope === 'end_user' ? subjectId : undefined,
    });
  }

  function closeOAuthAppDialog() {
    setOauthAppTarget(null);
    setOauthAuthorizeUrl(null);
    resetOAuthClientFields();
  }

  function findCatalogConnector(service: string): CatalogConnector | undefined {
    return workspaceApps.find((item) => item.service === service) ?? connectors.find((item) => item.service === service);
  }

  function beginConnectorConnect(
    item: CatalogConnector,
    preferredAuthMode?: string,
    scopeOpts?: { scope: 'workspace' | 'end_user'; subjectId?: string },
  ) {
    if (
      scopeOpts?.scope === 'end_user' &&
      serviceBlocksEndUserAuthorization(item.service)
    ) {
      toast.error(c.catalog.workspace_shared_blocks_end_user);
      return;
    }
    const modes = authModesForConnector(item.auth);
    const mode =
      preferredAuthMode && modes.includes(preferredAuthMode) ? preferredAuthMode : modes[0];
    setEditingConnection(null);
    if (scopeOpts) {
      setPendingConnectScope(scopeOpts.scope);
      setPendingConnectSubjectId(scopeOpts.subjectId ?? '');
    } else {
      setPendingConnectScope('workspace');
      setPendingConnectSubjectId('');
    }
    setSelectedConnector(item);
    setConnAuthMode(mode);
    setOauthAuthorizeUrl(null);
    setOauthUrlBuildAttempted(false);
    resetOAuthClientFields();
    applyConnectFormForAuth(item, mode);
    void loadOAuthConfigForService(item.service);
  }

  function beginConnectorEdit(item: CatalogConnector, existing: StoredConnection) {
    const modes = authModesForConnector(item.auth);
    const mode = modes.includes(existing.auth_type) ? existing.auth_type : modes[0];
    setEditingConnection(existing);
    setSelectedConnector(item);
    setConnAuthMode(mode);
    setOauthAuthorizeUrl(null);
    applyConnectFormFromConnection(item, mode, existing);
    void loadOAuthConfigForService(item.service);
  }

  function handleConnectAuthModeChange(authMode: string) {
    if (!selectedConnector || authorizationAuthModeLocked) return;
    setConnAuthMode(authMode);
    setOauthAuthorizeUrl(null);
    if (editingConnection) {
      applyConnectFormFromConnection(selectedConnector, authMode, editingConnection);
    } else {
      applyConnectFormForAuth(selectedConnector, authMode);
    }
  }

  const isAuthorizationConnectFlow = !panel && catalogSection === 'authorization';
  const oauthAppConfigured =
    Boolean(oauthClientId.trim()) && oauthHasSavedSecret;
  const authorizationAuthModeLocked = isAuthorizationAuthModeLocked(
    isAuthorizationConnectFlow,
    selectedConnector,
    editingConnection,
    oauthAppConfigured,
  );

  const connectAuthEntries = selectedConnector
    ? connectorAuthCatalogEntries(selectedConnector.auth)
    : [];
  const connectAuthEntry = selectedConnector
    ? findAuthCatalogEntry(selectedConnector.auth, connAuthMode)
    : undefined;
  const connectUsesStructuredFields =
    Boolean(connectAuthEntry && hasStructuredAuthForm(connectAuthEntry) && !connectFormUseJson);
  const oauth2ManifestOnly = isOAuth2ConnectManifestOnly(connectAuthEntry);
  const authModeLabels = c.catalog.auth_modes;

  function labelForAuthMode(
    item: CatalogConnector | null,
    authMode: string,
  ): string {
    const entry = findAuthCatalogEntry(item?.auth, authMode);
    return authModeDisplayLabel(authMode, entry?.display_name, authModeLabels);
  }

  useEffect(() => {
    if (!authorizationAuthModeLocked || !selectedConnector) {
      return;
    }
    const oauthMode = preferredOAuthAuthMode(selectedConnector.auth);
    if (!oauthMode || connAuthMode === oauthMode) {
      return;
    }
    setConnAuthMode(oauthMode);
    if (editingConnection) {
      applyConnectFormFromConnection(selectedConnector, oauthMode, editingConnection);
    } else {
      applyConnectFormForAuth(selectedConnector, oauthMode);
    }
  }, [
    authorizationAuthModeLocked,
    selectedConnector,
    editingConnection,
    oauthClientId,
    oauthHasSavedSecret,
    connAuthMode,
  ]);

  async function handleSaveConnection() {
    if (!workspaceId || !selectedConnector) return;
    setSavingConn(true);
    try {
      let cfg: Record<string, unknown>;
      let creds: Record<string, unknown>;
      if (connectUsesStructuredFields && connectAuthEntry) {
        cfg = buildObjectFromAuthFields(
          connectAuthEntry.connection_config,
          connConfigFieldValues,
        );
        creds = buildObjectFromAuthFields(connectAuthEntry.credentials, connCredFieldValues);
      } else {
        cfg = JSON.parse(connConfigJson || '{}') as Record<string, unknown>;
        creds = JSON.parse(connCredsJson || '{}') as Record<string, unknown>;
      }
      const credsBlank =
        connectUsesStructuredFields && connectAuthEntry
          ? authCredentialFieldsAreBlank(connectAuthEntry.credentials, connCredFieldValues)
          : parsedCredentialJsonIsBlank(connCredsJson);
      const scope = resolveConnectScope();
      const subjectId = resolveConnectSubjectId();
      if (scope === 'end_user' && serviceBlocksEndUserAuthorization(selectedConnector.service)) {
        toast.error(c.catalog.workspace_shared_blocks_end_user);
        return;
      }
      if (scope === 'end_user' && !subjectId) {
        toast.error(c.catalog.subject_id_required);
        return;
      }
      await workspaceOpenApiPUT(
        workspaceId,
        `connectors/connections/${selectedConnector.service}`,
        {
          body: {
            auth_type: connAuthMode,
            connection_config: cfg,
            credentials: credsBlank ? {} : creds,
            connection_scope: scope,
            ...(scope === 'end_user' && subjectId ? { subject_id: subjectId } : {}),
          },
        },
      );
      closeConnectDialog();
      await loadCatalogAndConnections();
    } catch (err) {
      toast.error(formatUserFacingApiError(err, locale as Locale));
    } finally {
      setSavingConn(false);
    }
  }

  function connectionQueryParams(conn: StoredConnection): {
    connection_scope: 'workspace' | 'end_user';
    subject_id?: string;
  } {
    const scope = conn.connection_scope ?? 'workspace';
    if (scope === 'end_user' && conn.subject_id) {
      return { connection_scope: 'end_user', subject_id: conn.subject_id };
    }
    return { connection_scope: 'workspace' };
  }

  async function handleCheckConnection(conn: StoredConnection) {
    if (!workspaceId) return;
    const key = connectionStorageKey(conn);
    setCheckingKey(key);
    try {
      await workspaceOpenApiPOST(
        workspaceId,
        `connectors/connections/${conn.service}/check`,
        { params: { query: connectionQueryParams(conn) } },
      );
      toast.success(c.catalog.check_success);
      await loadCatalogAndConnections();
    } catch (err) {
      toast.error(formatUserFacingApiError(err, locale as Locale));
    } finally {
      setCheckingKey(null);
    }
  }

  async function handleDeleteConnection(conn: StoredConnection) {
    if (!workspaceId) return;
    try {
      await workspaceOpenApiDELETE(
        workspaceId,
        `connectors/connections/${conn.service}`,
        { params: { query: connectionQueryParams(conn) } },
      );
      await loadCatalogAndConnections();
    } catch (err) {
      toast.error(formatUserFacingApiError(err, locale as Locale));
    }
  }

  async function handleInstallWorkspaceApp(service: string) {
    if (!workspaceId) return;
    setAppActionService(service);
    try {
      await workspaceOpenApiPOST(workspaceId, `connectors/policy/providers/${service}/enable`, {});
      toast.success(c.catalog.app_added_toast);
      setAddAppDialogOpen(false);
      setAddAppSearchQuery('');
      setCatalogSection('connectors');
      await loadCatalogAndConnections();
    } catch (err) {
      toast.error(formatUserFacingApiError(err, locale as Locale));
    } finally {
      setAppActionService(null);
    }
  }

  async function handleActivateWorkspaceApp(service: string) {
    if (!workspaceId) return;
    setAppActionService(service);
    try {
      await workspaceOpenApiPOST(workspaceId, `connectors/policy/providers/${service}/enable`, {});
      toast.success(c.catalog.app_activated_toast);
      await loadCatalogAndConnections();
    } catch (err) {
      toast.error(formatUserFacingApiError(err, locale as Locale));
    } finally {
      setAppActionService(null);
    }
  }

  async function handleSoftDisableWorkspaceApp(service: string) {
    if (!workspaceId) return;
    setAppActionService(service);
    try {
      await workspaceOpenApiPOST(workspaceId, `connectors/policy/providers/${service}/disable`, {});
      toast.success(c.catalog.app_disabled_toast);
      await loadCatalogAndConnections();
    } catch (err) {
      toast.error(formatUserFacingApiError(err, locale as Locale));
    } finally {
      setAppActionService(null);
    }
  }

  async function handleDeleteWorkspaceApp(service: string) {
    if (!workspaceId) return;
    setAppActionService(service);
    try {
      await workspaceOpenApiDELETE(workspaceId, `connectors/policy/providers/${service}`);
      toast.success(c.catalog.app_deleted_toast);
      await loadCatalogAndConnections();
    } catch (err) {
      toast.error(formatUserFacingApiError(err, locale as Locale));
    } finally {
      setAppActionService(null);
    }
  }

  function beginOAuthAppSetup(item: CatalogConnector) {
    setOauthAppTarget(item);
    setOauthAuthorizeUrl(null);
    resetOAuthClientFields();
    void loadOAuthConfigForService(item.service);
  }

  async function handleDeleteMapping(mappingId: string) {
    if (!workspaceId) return;
    setDeletingMappingId(mappingId);
    try {
      await workspaceOpenApiDELETE(workspaceId, `connectors/table-mappings/${mappingId}`);
      toast.success(c.mappings.deleted_toast);
      setDeleteMappingId(null);
      await loadMappings();
    } catch (err) {
      toast.error(formatUserFacingApiError(err, locale as Locale));
    } finally {
      setDeletingMappingId(null);
    }
  }

  async function handleSyncMapping(mappingId: string) {
    if (!workspaceId) return;
    setSyncingId(mappingId);
    try {
      const stats = await workspaceOpenApiPOST<{
        fetched_rows: number;
        added: number;
        updated: number;
        unchanged: number;
        deleted: number;
      }>(workspaceId, `connectors/table-mappings/${mappingId}/sync`);
      toast.success(
        fmt(c.mappings.sync_result_summary, {
          fetched: stats.fetched_rows,
          added: stats.added,
          updated: stats.updated,
          unchanged: stats.unchanged,
          deleted: stats.deleted,
        }),
      );
      await loadMappings();
    } catch (err) {
      toast.error(formatUserFacingApiError(err, locale as Locale));
    } finally {
      setSyncingId(null);
    }
  }

  async function handleSavePolicy() {
    if (!workspaceId) return;
    try {
      const trimmed = allowedProvidersInput.trim();
      const allowed =
        trimmed === '*' || !trimmed
          ? '*'
          : trimmed
              .split(',')
              .map((s) => s.trim())
              .filter(Boolean);
      const actionPolicy = JSON.parse(actionPolicyInput || '{}') as Record<string, unknown>;
      await workspaceOpenApiPUT(workspaceId, 'connectors/policy', {
        body: {
          allowed_providers: allowed,
          action_policy: actionPolicy,
        },
      });
      toast.success(c.policy.saved_toast);
      await loadPolicyAndOutbox();
    } catch (err) {
      toast.error(formatUserFacingApiError(err, locale as Locale));
    }
  }

  async function persistOAuthAppConfig(service: string): Promise<boolean> {
    if (!workspaceId) {
      return false;
    }
    if (!oauthClientId.trim() || (!oauthClientSecret.trim() && !oauthHasSavedSecret)) {
      toast.error(c.catalog.oauth_client_required);
      return false;
    }
    const redirectUri = workspaceConnectorOAuthRedirectUri(workspaceId);
    await workspaceOpenApiPUT(workspaceId, `connectors/oauth-configs/${service}`, {
      body: {
        client_id: oauthClientId.trim(),
        client_secret: oauthClientSecret.trim() || null,
        redirect_uri: redirectUri,
      },
    });
    setOauthHasSavedSecret(true);
    return true;
  }

  async function handleSaveOAuthApp() {
    if (!oauthAppTarget) {
      return;
    }
    setSavingOAuthApp(true);
    try {
      const ok = await persistOAuthAppConfig(oauthAppTarget.service);
      if (ok) {
        toast.success(c.catalog.oauth_app_saved);
        closeOAuthAppDialog();
      }
    } catch (err) {
      toast.error(formatUserFacingApiError(err, locale as Locale));
    } finally {
      setSavingOAuthApp(false);
    }
  }

  async function requestConnectorOAuthAuthorizeUrl(opts: {
    service: string;
    auth: ConnectorAuthCatalogEntry[] | undefined;
        connectionConfig: Record<string, unknown>;
    scope: 'workspace' | 'end_user';
    subjectId: string;
    fromAuthorization: boolean;
    clientId: string;
    hasSavedSecret: boolean;
    clientSecret?: string;
  }): Promise<string | null> {
    if (!workspaceId) {
      return null;
    }
    const hasOAuthAppConfigured =
      Boolean(opts.clientId.trim()) &&
      (opts.hasSavedSecret ||
        (!opts.fromAuthorization && Boolean(opts.clientSecret?.trim())));
    if (!hasOAuthAppConfigured) {
      toast.error(
        opts.fromAuthorization
          ? c.catalog.oauth_app_required_on_connectors
          : c.catalog.oauth_client_required,
      );
      return null;
    }
    const redirectUri = workspaceConnectorOAuthRedirectUri(workspaceId);
    if (
      !opts.fromAuthorization &&
      (opts.clientSecret?.trim() || !opts.hasSavedSecret)
    ) {
      const ok = await persistOAuthAppConfig(opts.service);
      if (!ok) {
        return null;
      }
    }
    const cfg = opts.connectionConfig;
    const needsPkce = connectorAuthNeedsPkce(opts.auth);
    const state = generateOAuthState();
    let codeVerifier: string | undefined;
    let codeChallenge: string | undefined;
    if (needsPkce) {
      const pkce = await generatePkcePair();
      codeVerifier = pkce.verifier;
      codeChallenge = pkce.challenge;
    }
    const endUserSubjectId = opts.scope === 'end_user' ? opts.subjectId.trim() : '';
    if (opts.scope === 'end_user' && !endUserSubjectId) {
      toast.error(c.catalog.subject_id_required);
      return null;
    }
    if (endUserSubjectId) {
      const res = await workspaceOpenApiPOST<{ authorize_url: string; state: string }>(
        workspaceId,
        `connectors/embed/oauth/${opts.service}/authorize-url`,
        {
          body: {
            subject_id: endUserSubjectId,
            redirect_uri: redirectUri,
            connection_config: cfg,
            code_challenge: codeChallenge ?? null,
          },
        },
      );
      const authorizeUrl = res.authorize_url;
      const resolvedState = res.state ?? state;
      savePendingConnectorOAuth({
        workspaceId,
        service: opts.service,
        connectionConfig: cfg,
        state: resolvedState,
        redirectUri,
        codeVerifier,
        endUserSubjectId,
        returnTo: 'connectors-authorization',
      });
      return authorizeUrl;
    }
    const res = await workspaceOpenApiPOST<{ authorize_url: string; state: string }>(
      workspaceId,
      `connectors/oauth/${opts.service}/authorize-url`,
      {
        body: {
          state,
          redirect_uri: redirectUri,
          connection_config: cfg,
          code_challenge: codeChallenge ?? null,
        },
      },
    );
    const authorizeUrl = res.authorize_url;
    const resolvedState = res.state ?? state;
    savePendingConnectorOAuth({
      workspaceId,
      service: opts.service,
      connectionConfig: cfg,
      state: resolvedState,
      redirectUri,
      codeVerifier,
      returnTo: 'connectors-authorization',
    });
    return authorizeUrl;
  }

  function resolveConnectDialogConnectionConfig(): Record<string, unknown> {
    if (connectUsesStructuredFields && connectAuthEntry) {
      return buildObjectFromAuthFields(
        connectAuthEntry.connection_config,
        connConfigFieldValues,
      );
    }
    try {
      return JSON.parse(connConfigJson || '{}') as Record<string, unknown>;
    } catch {
      return {};
    }
  }

  async function buildAuthorizationOAuthUrl(opts: {
    clientId: string;
    hasSavedSecret: boolean;
    silent?: boolean;
  }) {
    if (!workspaceId || !selectedConnector) {
      return;
    }
    if (!isAuthorizationConnectFlow || connAuthMode !== 'oauth2') {
      return;
    }
    setBuildingOAuthUrl(true);
    setOauthAuthorizeUrl(null);
    try {
      const authorizeUrl = await requestConnectorOAuthAuthorizeUrl({
        service: selectedConnector.service,
        auth: selectedConnector.auth,
                connectionConfig: resolveConnectDialogConnectionConfig(),
        scope: resolveConnectScope(),
        subjectId: resolveConnectSubjectId(),
        fromAuthorization: true,
        clientId: opts.clientId,
        hasSavedSecret: opts.hasSavedSecret,
      });
      if (authorizeUrl) {
        setOauthAuthorizeUrl(authorizeUrl);
        if (!opts.silent) {
          toast.success(c.catalog.oauth_url_generated);
        }
      }
    } catch (err) {
      toast.error(formatUserFacingApiError(err, locale as Locale));
    } finally {
      setBuildingOAuthUrl(false);
    }
  }

  useEffect(() => {
    if (!workspaceId || !selectedConnector) {
      return;
    }
    if (!isAuthorizationConnectFlow || connAuthMode !== 'oauth2') {
      return;
    }
    if (!oauthClientId.trim() || !oauthHasSavedSecret) {
      return;
    }
    if (oauthConfigLoadingFor === selectedConnector.service) {
      return;
    }

    let cancelled = false;
    setBuildingOAuthUrl(true);
    setOauthAuthorizeUrl(null);

    const scope = resolveConnectScope();
    const subjectId = resolveConnectSubjectId();

    void (async () => {
      try {
        const authorizeUrl = await requestConnectorOAuthAuthorizeUrl({
          service: selectedConnector.service,
          auth: selectedConnector.auth,
                    connectionConfig: resolveConnectDialogConnectionConfig(),
          scope,
          subjectId,
          fromAuthorization: true,
          clientId: oauthClientId,
          hasSavedSecret: oauthHasSavedSecret,
        });
        if (!cancelled && authorizeUrl) {
          setOauthAuthorizeUrl(authorizeUrl);
        }
      } catch (err) {
        if (!cancelled) {
          toast.error(formatUserFacingApiError(err, locale as Locale));
        }
      } finally {
        if (!cancelled) {
          setBuildingOAuthUrl(false);
          setOauthUrlBuildAttempted(true);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [
    workspaceId,
    selectedConnector,
    panel,
    catalogSection,
    connAuthMode,
    oauthClientId,
    oauthHasSavedSecret,
    oauthConfigLoadingFor,
    pendingConnectScope,
    pendingConnectSubjectId,
    editingConnection,
    connConfigJson,
    connConfigFieldValues,
    connectFormUseJson,
    locale,
  ]);

  async function handleBuildOAuthUrl() {
    if (!workspaceId || !selectedConnector) return;
    const fromAuthorization = !panel && catalogSection === 'authorization';
    if (fromAuthorization && connAuthMode === 'oauth2') {
      await buildAuthorizationOAuthUrl({
        clientId: oauthClientId,
        hasSavedSecret: oauthHasSavedSecret,
        silent: false,
      });
      return;
    }
    try {
      const authorizeUrl = await requestConnectorOAuthAuthorizeUrl({
        service: selectedConnector.service,
        auth: selectedConnector.auth,
                connectionConfig: resolveConnectDialogConnectionConfig(),
        scope: resolveConnectScope(),
        subjectId: resolveConnectSubjectId(),
        fromAuthorization,
        clientId: oauthClientId,
        hasSavedSecret: oauthHasSavedSecret,
        clientSecret: oauthClientSecret,
      });
      if (authorizeUrl) {
        setOauthAuthorizeUrl(authorizeUrl);
        toast.success(c.catalog.oauth_url_generated);
      }
    } catch (err) {
      toast.error(formatUserFacingApiError(err, locale as Locale));
    }
  }

  async function handleReauthorizeConnection(item: CatalogConnector, conn: StoredConnection) {
    if (!workspaceId) {
      return;
    }
    if (conn.auth_type === 'oauth2') {
      const key = connectionStorageKey(conn);
      setReauthorizingKey(key);
      try {
        const oauthRes = await workspaceOpenApiGET<{
          oauth_config: { client_id?: string; has_client_secret?: boolean };
        }>(workspaceId, `connectors/oauth-configs/${conn.service}`);
        const clientId = oauthRes.oauth_config?.client_id?.trim() ?? '';
        const hasSavedSecret = Boolean(oauthRes.oauth_config?.has_client_secret);
        const scope = conn.connection_scope === 'end_user' ? 'end_user' : 'workspace';
        const subjectId = scope === 'end_user' ? (conn.subject_id ?? '').trim() : '';
        const authorizeUrl = await requestConnectorOAuthAuthorizeUrl({
          service: conn.service,
          auth: item.auth,
                    connectionConfig: conn.connection_config ?? {},
          scope,
          subjectId,
          fromAuthorization: true,
          clientId,
          hasSavedSecret,
        });
        if (authorizeUrl) {
          window.location.assign(authorizeUrl);
        }
      } catch (err) {
        toast.error(formatUserFacingApiError(err, locale as Locale));
      } finally {
        setReauthorizingKey(null);
      }
      return;
    }
    beginConnectorEdit(item, conn);
  }

  async function handleRunTool() {
    if (!workspaceId) return;
    setRunningTool(true);
    try {
      const args = JSON.parse(toolArgsJson || '{}') as Record<string, unknown>;
      const res = await workspaceOpenApiPOST(workspaceId, 'connectors/tools/execute', {
        body: {
          service: toolService.trim(),
          tool_id: toolId.trim(),
                    arguments: args,
        },
      });
      setToolResultJson(JSON.stringify(res, null, 2));
    } catch (err) {
      toast.error(formatUserFacingApiError(err, locale as Locale));
    } finally {
      setRunningTool(false);
    }
  }

  function renderWorkspaceAppCard(item: CatalogConnector) {
    const firstAuthEntry = connectorAuthCatalogEntries(item.auth)[0];
    const firstAuth = firstAuthEntry?.auth_mode ?? 'custom';
    const firstAuthLabel = authModeDisplayLabel(
      firstAuth,
      firstAuthEntry?.display_name,
      authModeLabels,
    );
    const configuredForService = configuredByService.get(item.service) ?? [];
    const needsCredentials = catalogProviderNeedsCredentials(item);
    const supportsOAuth = catalogProviderSupportsOAuth(item);
    const supportsDataSync = (item.streams?.length ?? 0) > 0;
    const appBusy = appActionService === item.service;
    const appDisabled = disabledAppServices.has(item.service);
    return (
      <div
        key={item.service}
        className={cn(resourceCardSurfaceClass, 'flex flex-col justify-between gap-3 p-3.5')}
        data-testid={`workspace-app-card-${item.service}`}
      >
        <div>
          <div className="flex items-center justify-between gap-2">
            <span className="font-medium text-sm text-foreground">{item.display_name}</span>
            <div className="flex shrink-0 flex-wrap items-center justify-end gap-1">
              {appDisabled ? (
                <Badge variant="outline" className="text-[10px]">
                  {c.catalog.app_disabled_badge}
                </Badge>
              ) : null}
              {!needsCredentials ? (
                <Badge variant="secondary" className="text-[10px]">
                  {c.catalog.app_no_credentials_badge}
                </Badge>
              ) : null}
              {configuredForService.length > 0 ? (
                <Badge
                  variant="outline"
                  className="badge-status-success text-[10px]"
                  data-testid={`workspace-app-has-connections-${item.service}`}
                >
                  {c.catalog.configured_card_badge}
                </Badge>
              ) : null}
              <Badge variant="secondary" className="text-[10px]">
                {firstAuthLabel}
              </Badge>
              <Badge
                variant="outline"
                className={cn('text-[10px]', supportsDataSync && 'badge-status-success')}
                data-testid={`connector-data-sync-${item.service}-${supportsDataSync ? 'yes' : 'no'}`}
              >
                {supportsDataSync
                  ? c.catalog.data_sync_supported
                  : c.catalog.data_sync_not_supported}
              </Badge>
            </div>
          </div>
          <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{item.description}</p>
          {configuredForService.length > 0 ? (
            <p className="mt-1.5 text-[11px] text-muted-foreground">
              {fmt(c.catalog.configured_card_connections, {
                count: configuredForService.length,
                names: configuredForService.map((conn) => conn.service).join(', '),
              })}
            </p>
          ) : null}
          {(item.tools?.length ?? 0) > 0 ? (
            <p className="mt-2 text-[11px] text-muted-foreground">
              {fmt(c.catalog.tools_badge, { count: item.tools?.length ?? 0 })}
            </p>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-2 pt-1">
            {supportsOAuth ? (
              <Button
                size="sm"
                variant="outline"
                disabled={appDisabled}
                onClick={() => beginOAuthAppSetup(item)}
                data-testid={`oauth-app-${item.service}`}
              >
                {c.catalog.app_oauth_button}
              </Button>
            ) : null}
            {needsCredentials && workspaceId && !appDisabled ? (
              <Button size="sm" variant="secondary" asChild>
                <Link
                  to={workspaceConnectorsAuthorizationHref(workspaceId, { service: item.service })}
                  data-testid={`workspace-app-authorization-${item.service}`}
                >
                  {c.catalog.app_go_authorization}
                </Link>
              </Button>
            ) : null}
            {appDisabled ? (
              <Button
                size="sm"
                variant="secondary"
                disabled={appBusy}
                onClick={() => void handleActivateWorkspaceApp(item.service)}
                data-testid={`activate-workspace-app-${item.service}`}
              >
                {c.catalog.app_activate_button}
              </Button>
            ) : (
              <Button
                size="sm"
                variant="outline"
                disabled={appBusy}
                onClick={() => void handleSoftDisableWorkspaceApp(item.service)}
                data-testid={`soft-disable-workspace-app-${item.service}`}
              >
                {c.catalog.app_soft_disable_button}
              </Button>
            )}
            <Button
              size="sm"
              variant="ghost"
              disabled={appBusy}
              onClick={() => void handleDeleteWorkspaceApp(item.service)}
              data-testid={`delete-workspace-app-${item.service}`}
            >
              {c.catalog.app_delete_button}
            </Button>
        </div>
      </div>
    );
  }

  function renderConfiguredConnectionRow(conn: StoredConnection) {
    const key = connectionStorageKey(conn);
    const scope = conn.connection_scope ?? 'workspace';
    const isWorkspaceScope = scope !== 'end_user';
    const rowTestId =
      scope === 'end_user'
        ? `configured-connection-${conn.service}-end-user`
        : `configured-connection-${conn.service}`;
    return (
      <div
        key={key}
        className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm"
        data-testid={rowTestId}
      >
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
          <Badge
            variant={scope === 'end_user' ? 'secondary' : 'outline'}
            className="text-[10px]"
          >
            {scope === 'end_user' ? c.catalog.scope_end_user_badge : c.catalog.scope_workspace_badge}
          </Badge>
          <Badge variant="outline" className="font-mono text-xs">
            {conn.service}
          </Badge>
          <span className="font-medium text-foreground">{conn.service}</span>
          <span className="text-xs text-muted-foreground">({conn.auth_type})</span>
          {scope === 'end_user' && conn.subject_id ? (
            <span className="truncate font-mono text-[11px] text-muted-foreground">
              {fmt(c.catalog.scope_subject_label, { id: conn.subject_id })}
            </span>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Button
            size="sm"
            variant="outline"
            disabled={reauthorizingKey === key}
            onClick={() => {
              const catalogItem = findCatalogConnector(conn.service);
              if (catalogItem) {
                void handleReauthorizeConnection(catalogItem, conn);
              } else {
                toast.error(c.catalog.reauthorize_catalog_missing);
              }
            }}
            data-testid={
              isWorkspaceScope
                ? `reauthorize-connection-${conn.service}`
                : `reauthorize-end-user-connection-${conn.service}`
            }
          >
            {reauthorizingKey === key ? c.catalog.reauthorizing : c.catalog.reauthorize_button}
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={checkingKey === key}
            onClick={() => void handleCheckConnection(conn)}
          >
            {checkingKey === key ? c.catalog.checking : c.catalog.check_button}
          </Button>
          <Button size="sm" variant="ghost" onClick={() => void handleDeleteConnection(conn)}>
            {c.catalog.delete_button}
          </Button>
        </div>
      </div>
    );
  }

  const connectAuthEntriesForDialog = (() => {
    let entries = isAuthorizationConnectFlow
      ? connectAuthEntries
      : connectAuthEntries.filter(
          (entry) => entry.auth_mode !== 'oauth2' && entry.auth_mode !== 'oauth2_cc',
        );
    if (authorizationAuthModeLocked) {
      const oauthMode = selectedConnector
        ? preferredOAuthAuthMode(selectedConnector.auth)
        : undefined;
      if (oauthMode) {
        entries = entries.filter((entry) => entry.auth_mode === oauthMode);
      }
    }
    return entries;
  })();
  const showConnectAuthModeSelector =
    connectAuthEntriesForDialog.length > 1 && !authorizationAuthModeLocked;
  const oauthUserAuthBlockedOnConnectorsTab =
    !isAuthorizationConnectFlow &&
    (connAuthMode === 'oauth2' || connAuthMode === 'oauth2_cc');
  const authorizationOAuthBrowserFlow =
    isAuthorizationConnectFlow && connAuthMode === 'oauth2';
  const hideAuthorizationOAuthDialogFields =
    authorizationOAuthBrowserFlow && oauth2ManifestOnly && !editingConnection;
  const oauthAuthorizeUrlLoading =
    authorizationOAuthBrowserFlow &&
    Boolean(oauthClientId.trim()) &&
    oauthHasSavedSecret &&
    (buildingOAuthUrl ||
      oauthConfigLoadingFor === selectedConnector?.service ||
      !oauthUrlBuildAttempted);
  const showOAuthAuthorizeUrlFailed =
    authorizationOAuthBrowserFlow &&
    oauthUrlBuildAttempted &&
    !buildingOAuthUrl &&
    !oauthAuthorizeUrl &&
    Boolean(oauthClientId.trim()) &&
    oauthHasSavedSecret;

  if (!workspaceId) return null;

  const workspaceTab: CatalogSection | ConnectorPanel = panel ?? catalogSection;

  function onWorkspaceTabChange(value: string) {
    if (!workspaceId) return;
    if (value === 'connectors' || value === 'authorization') {
      const next = new URLSearchParams(searchParams);
      next.set('section', value);
      const q = next.toString();
      navigate(`${workspaceConnectorHomePath(workspaceId)}?${q}`);
      return;
    }
    const nextPanel = parseConnectorPanel(value);
    if (nextPanel) {
      navigate(workspaceConnectorPanelPath(workspaceId, nextPanel));
    }
  }

  return (
    <ConsolePageLayout
      crumbs={[
        { label: t.core.workspace_nav.platform.workspaces, to: '/workspaces' },
        { label: getWorkspace(workspaceId)?.name ?? workspaceId, to: workspacePath(workspaceId!, 'graph') },
        { label: t.core.workspace_nav.workspace_zones.knowledge, to: workspaceConnectorHomePath(workspaceId!) },
        { label: t.connectors.menu.connections_sync },
      ]}
      subtitle={t.connectors.page.subtitle}
    >
      <Tabs
        value={workspaceTab}
        onValueChange={onWorkspaceTabChange}
        className="mb-4 min-w-0"
      >
        <TabsList className="h-auto flex-wrap" data-testid="connectors-workspace-tabs">
          <TabsTrigger value="connectors" data-testid="connectors-workspace-tab-connectors">
            {c.catalog.section_tabs.connectors}
          </TabsTrigger>
          <TabsTrigger value="authorization" data-testid="connectors-workspace-tab-authorization">
            {c.catalog.section_tabs.authorization}
          </TabsTrigger>
          <TabsTrigger value="policy" data-testid="connectors-workspace-tab-policy">
            {t.connectors.menu.connector_action_policy}
          </TabsTrigger>
          <TabsTrigger value="mappings" data-testid="connectors-workspace-tab-mappings">
            {t.connectors.menu.connector_stream_mappings}
          </TabsTrigger>
          <TabsTrigger value="runs" data-testid="connectors-workspace-tab-runs">
            {t.connectors.menu.connector_run_logs}
          </TabsTrigger>
        </TabsList>
      </Tabs>
      {!panel && catalogSection === 'connectors' ? (
        <div className="space-y-4" data-testid="connectors-panel-catalog">
              <DataPanel data-testid="connectors-catalog-section-enabled">
                <DataPanelHeader
                  title={c.catalog.workspace_apps_title}
                  subtitle={c.catalog.workspace_apps_subtitle}
                  actions={
                    <Button
                      size="sm"
                      onClick={() => setAddAppDialogOpen(true)}
                      data-testid="connectors-add-app-btn"
                    >
                      <PublicIcon name="plus-01" size={14} className="mr-1" />
                      {c.catalog.app_add_button}
                    </Button>
                  }
                />
                <DataPanelBody padded={false}>
                  <div className="border-b border-border px-4 py-3">
                    <Input
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder={c.catalog.search_placeholder}
                      className="max-w-md"
                      data-testid="connectors-enabled-search"
                    />
                  </div>
                  {connectionsLoading ? (
                    <p className="px-4 py-8 text-sm text-muted-foreground">
                      {t.core.common.loading}
                    </p>
                  ) : filteredWorkspaceApps.length === 0 ? (
                    <div className="flex flex-col items-center gap-3 px-4 py-8 text-center">
                      <p className="text-sm text-muted-foreground">{c.catalog.workspace_apps_empty}</p>
                      <Button size="sm" onClick={() => setAddAppDialogOpen(true)}>
                        <PublicIcon name="plus-01" size={14} className="mr-1" />
                        {c.catalog.app_add_button}
                      </Button>
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 gap-3 p-4 md:grid-cols-2 lg:grid-cols-3">
                      {filteredWorkspaceApps.map((item) => renderWorkspaceAppCard(item))}
                    </div>
                  )}
                </DataPanelBody>
              </DataPanel>
        </div>
      ) : null}

      {!panel && catalogSection === 'authorization' ? (
        <div className="space-y-4" data-testid="connectors-panel-authorization">
              <p
                className="rounded-lg border border-border bg-muted/10 px-4 py-3 text-sm text-muted-foreground"
                data-testid="connectors-scope-intro"
              >
                {c.catalog.authorization_section_subtitle}
                <span className="mt-2 block text-xs">{c.catalog.scope_intro_body}</span>
              </p>

              <DataPanel data-testid="connectors-catalog-section-authorizations">
                <DataPanelHeader
                  title={c.catalog.configured_authorizations_title}
                  subtitle={c.catalog.configured_authorizations_subtitle}
                  actions={
                    <Button
                      size="sm"
                      onClick={() => openAddAuthorizationDialog()}
                      data-testid="connectors-add-authorization-btn"
                    >
                      <PublicIcon name="plus-01" size={14} className="mr-1" />
                      {c.catalog.add_authorization_button}
                    </Button>
                  }
                />
                <DataPanelBody padded={false}>
                  {authorizationConnections.length === 0 ? (
                    <p className="px-4 py-6 text-sm text-muted-foreground">
                      {c.catalog.configured_authorizations_empty}
                    </p>
                  ) : (
                    <div className="divide-y divide-border">
                      {authorizationConnections.map((conn) => renderConfiguredConnectionRow(conn))}
                    </div>
                  )}
                </DataPanelBody>
              </DataPanel>
        </div>
      ) : null}

      {panel === 'mappings' ? (
        <div className="space-y-4" data-testid="connectors-panel-mappings">
          <DataPanel>
            <DataPanelHeader
              title={c.mappings.title}
              subtitle={c.mappings.subtitle}
              actions={
                <Button
                  size="sm"
                  onClick={() => openCreateMapping('auto')}
                  data-testid="create-table-mapping-btn"
                >
                  <PublicIcon name="plus-01" size={14} className="mr-1" />
                  {c.mappings.create_button}
                </Button>
              }
            />
            <DataPanelBody padded={false}>
              {mappings.length === 0 ? (
                <div className="flex flex-col items-center gap-3 px-4 py-8 text-center">
                  <p className="text-sm font-medium text-foreground">{c.mappings.empty_title}</p>
                  <p className="max-w-md text-xs text-muted-foreground">{c.mappings.empty_description}</p>
                  <div className="flex flex-wrap items-center justify-center gap-2 pt-1">
                    <Button
                      size="sm"
                      onClick={() => openCreateMapping('auto')}
                      data-testid="create-table-mapping-empty-btn"
                    >
                      <PublicIcon name="plus-01" size={14} className="mr-1" />
                      {c.mappings.create_button}
                    </Button>
                    {connections.length === 0 ? (
                      <Button size="sm" variant="outline" asChild>
                        <Link to={workspaceConnectorsAuthorizationHref(workspaceId)}>
                          {c.mappings.empty_open_authorization}
                        </Link>
                      </Button>
                    ) : null}
                  </div>
                </div>
              ) : (
                <div className="divide-y divide-border">
                  {mappings.map((m) => (
                    <div
                      key={m.id}
                      className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm"
                      data-testid={`table-mapping-row-${m.id}`}
                    >
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-medium text-foreground">
                            {m.external_table}
                          </span>
                          <span className="text-muted-foreground">→</span>
                          <Badge variant="outline" className="font-mono text-xs">
                            {m.target_class_uri}
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          {m.provider ? `${m.provider} · ` : ''}
                          {m.stream_name} · PK: {m.primary_key_column} · Label: {m.label_column} ·{' '}
                          {m.sync_direction === 'bidirectional'
                            ? fmt(c.mappings.direction_bidirectional, { mode: m.writeback_mode })
                            : c.mappings.direction_inbound}
                        </p>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <Button size="sm" variant="ghost" asChild>
                          <Link
                            to={workspaceConnectorMappingEditPath(workspaceId, m.id)}
                            data-testid={`edit-mapping-btn-${m.id}`}
                          >
                            {c.mappings.edit_button}
                          </Link>
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setDeleteMappingId(m.id)}
                          data-testid={`delete-mapping-btn-${m.id}`}
                        >
                          {c.mappings.delete_button}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={syncingId === m.id}
                          onClick={() => void handleSyncMapping(m.id)}
                          data-testid={`sync-mapping-btn-${m.id}`}
                        >
                          <PublicIcon name="sync" size={14} className="mr-1" />
                          {syncingId === m.id ? c.mappings.syncing : c.mappings.sync_button}
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </DataPanelBody>
          </DataPanel>
        </div>
      ) : null}

      {panel === 'policy' ? (
        <div className="space-y-4" data-testid="connectors-panel-policy">
          <DataPanel>
            <DataPanelHeader title={c.policy.title} subtitle={c.policy.subtitle} />
            <DataPanelBody>
              <div className="space-y-4">
                <div className="space-y-1.5">
                  <Label>{c.policy.platform_allowed_label}</Label>
                  <Input
                    value={platformAllowedDisplay}
                    readOnly
                    className="bg-muted/40"
                    data-testid="policy-platform-allowed-providers"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>{c.policy.allowed_providers_label}</Label>
                  <Input
                    value={allowedProvidersInput}
                    onChange={(e) => setAllowedProvidersInput(e.target.value)}
                    data-testid="policy-allowed-providers-input"
                  />
                  <p className="text-xs text-muted-foreground">{c.policy.allowed_providers_hint}</p>
                </div>
                <div className="space-y-1.5">
                  <Label>{c.policy.effective_allowed_label}</Label>
                  <Input
                    value={effectiveAllowedDisplay}
                    readOnly
                    className="bg-muted/40 font-mono text-xs"
                    data-testid="policy-effective-allowed-providers"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>{c.policy.action_policy_label}</Label>
                  <JsonEditor
                    height={140}
                    value={actionPolicyInput}
                    onChange={setActionPolicyInput}
                  />
                </div>
                <Button size="sm" onClick={() => void handleSavePolicy()} data-testid="save-connector-policy-btn">
                  {c.policy.save_policy}
                </Button>
              </div>
            </DataPanelBody>
          </DataPanel>

          <DataPanel>
            <DataPanelHeader title={c.policy.outbox_title} />
            <DataPanelBody padded={false}>
              {outboxItems.length === 0 ? (
                <p className="px-4 py-6 text-sm text-muted-foreground">{c.policy.outbox_empty}</p>
              ) : (
                <div className="divide-y divide-border">
                  {outboxItems.map((item) => (
                    <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm">
                      <div className="space-y-1">
                        <div className="font-mono text-xs text-muted-foreground">
                          {item.patch.provider} · {item.patch.external_table} ({item.patch.external_pk})
                        </div>
                        <div className="flex flex-wrap gap-2 font-mono text-xs">
                          {Object.entries(item.patch.changes ?? {}).map(([col, chg]) => (
                            <span key={col}>
                              <strong>{col}:</strong> {String(chg.old ?? '—')} → {String(chg.new ?? '—')}
                            </span>
                          ))}
                        </div>
                      </div>
                      <Badge variant="outline">{item.status}</Badge>
                    </div>
                  ))}
                </div>
              )}
            </DataPanelBody>
          </DataPanel>

          <DataPanel>
            <DataPanelHeader title={c.policy.tool_runner_title} />
            <DataPanelBody>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <div className="space-y-1">
                  <Label>{c.policy.tool_service_label}</Label>
                  <Input
                    value={toolService}
                    onChange={(e) => setToolService(e.target.value)}
                    data-testid="tool-runner-service-input"
                  />
                </div>
                <div className="space-y-1">
                  <Label>{c.policy.tool_id_label}</Label>
                  <Input
                    value={toolId}
                    onChange={(e) => setToolId(e.target.value)}
                    data-testid="tool-runner-id-input"
                  />
                </div>
                <div className="col-span-full space-y-1">
                  <Label>{c.policy.tool_args_label}</Label>
                  <JsonEditor
                    height={110}
                    value={toolArgsJson}
                    onChange={setToolArgsJson}
                  />
                </div>
                <div className="col-span-full flex items-center gap-3">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={runningTool}
                    onClick={() => void handleRunTool()}
                    data-testid="run-connector-tool-btn"
                  >
                    {runningTool ? c.policy.running_tool : c.policy.run_tool_button}
                  </Button>
                </div>
                {toolResultJson && (
                  <div className="col-span-full">
                    <JsonEditor
                      height={160}
                      readOnly
                      value={toolResultJson}
                    />
                  </div>
                )}
              </div>
            </DataPanelBody>
          </DataPanel>
        </div>
      ) : null}

      {panel === 'runs' ? (
        <div data-testid="connectors-panel-runs">
          <DataPanel>
            <DataPanelHeader title={c.runs.title} />
            <DataPanelBody padded={false}>
              {runs.length === 0 ? (
                <p className="px-4 py-6 text-sm text-muted-foreground">{c.runs.empty}</p>
              ) : (
                <div className="divide-y divide-border">
                  {runs.map((run) => (
                    <div key={run.id} className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm">
                      <div className="flex items-center gap-3">
                        <Badge variant={run.ok ? 'secondary' : 'destructive'}>
                          {run.ok ? c.runs.status_ok : c.runs.status_failed}
                        </Badge>
                        <span className="font-mono text-xs font-medium">{run.service}</span>
                        <span className="text-xs text-muted-foreground">{run.operation_kind}</span>
                        <span className="font-mono text-xs text-muted-foreground">{run.target_id}</span>
                      </div>
                      <span className="text-xs text-muted-foreground">
                        {formatLocaleDateTime(locale as Locale, run.started_at)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </DataPanelBody>
          </DataPanel>
        </div>
      ) : null}

      <Dialog
        open={addAuthOpen}
        onOpenChange={(open) => {
          setAddAuthOpen(open);
          if (!open) {
            setAddAuthSearch('');
          }
        }}
      >
        <DialogContent
          className="flex max-h-[85vh] max-w-2xl flex-col overflow-hidden"
          data-testid="connectors-add-authorization-dialog"
        >
          <DialogHeader>
            <DialogTitle>{c.catalog.add_authorization_dialog_title}</DialogTitle>
            <p className="text-sm text-muted-foreground">{c.catalog.add_authorization_dialog_subtitle}</p>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="space-y-1">
              <Label>{c.catalog.add_authorization_scope_label}</Label>
              <Select
                value={addAuthScope}
                onValueChange={(value) => setAddAuthScope(value as 'workspace' | 'end_user')}
              >
                <SelectTrigger data-testid="add-authorization-scope">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="workspace">{c.catalog.add_authorization_scope_workspace}</SelectItem>
                  <SelectItem value="end_user">{c.catalog.add_authorization_scope_end_user}</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">{c.catalog.scope_exclusive_hint}</p>
            </div>
            {addAuthScope === 'end_user' ? (
              <div className="space-y-1">
                <Label htmlFor="add-auth-subject-id">{c.catalog.end_user_subject_label}</Label>
                <Input
                  id="add-auth-subject-id"
                  value={addAuthSubject}
                  onChange={(e) => setAddAuthSubject(e.target.value)}
                  className="font-mono text-sm"
                  data-testid="add-authorization-subject-id"
                />
                <p className="text-xs text-muted-foreground">{c.catalog.end_user_subject_hint}</p>
              </div>
            ) : null}
            <Input
              value={addAuthSearch}
              onChange={(e) => setAddAuthSearch(e.target.value)}
              placeholder={c.catalog.search_placeholder}
              data-testid="add-authorization-search"
            />
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {addAuthProviders.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">
                {addAuthScope === 'end_user' && workspaceSharedServices.size > 0
                  ? c.catalog.add_authorization_dialog_empty_end_user_blocked
                  : c.catalog.add_authorization_dialog_empty}
              </p>
            ) : (
              <div className="divide-y divide-border rounded-md border border-border">
                {addAuthProviders.map((item) => (
                  <button
                    key={item.service}
                    type="button"
                    className="flex w-full items-start gap-3 px-4 py-3 text-left text-sm transition-colors hover:bg-muted/50"
                    onClick={() => confirmAddAuthorization(item)}
                    data-testid={`add-authorization-pick-${item.service}`}
                  >
                    <span className="font-medium text-foreground">
                      {item.display_name ?? item.service}
                    </span>
                    <span className="font-mono text-xs text-muted-foreground">{item.service}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog
        open={addAppDialogOpen}
        onOpenChange={(open) => {
          setAddAppDialogOpen(open);
          if (!open) {
            setAddAppSearchQuery('');
          }
        }}
      >
        <DialogContent className="max-h-[85vh] max-w-2xl overflow-hidden flex flex-col" data-testid="connectors-add-app-dialog">
          <DialogHeader>
            <DialogTitle>{c.catalog.app_add_dialog_title}</DialogTitle>
            <p className="text-sm text-muted-foreground">{c.catalog.app_add_dialog_subtitle}</p>
          </DialogHeader>
          <div className="py-2">
            <Input
              value={addAppSearchQuery}
              onChange={(e) => setAddAppSearchQuery(e.target.value)}
              placeholder={c.catalog.search_placeholder}
              data-testid="connectors-add-app-search"
            />
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {installableCatalogConnectors.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">
                {c.catalog.app_add_dialog_empty}
              </p>
            ) : (
              <div className="divide-y divide-border rounded-md border border-border">
                {installableCatalogConnectors.map((item) => (
                  <button
                    key={item.service}
                    type="button"
                    className="flex w-full items-start gap-3 px-4 py-3 text-left text-sm transition-colors hover:bg-muted/50 disabled:opacity-50"
                    disabled={appActionService === item.service}
                    onClick={() => void handleInstallWorkspaceApp(item.service)}
                    data-testid={`add-app-pick-${item.service}`}
                  >
                    <span className="min-w-0 flex-1">
                      <span className="font-medium text-foreground">{item.display_name}</span>
                      <span className="mt-0.5 block font-mono text-[11px] text-muted-foreground">
                        {item.service}
                      </span>
                      {item.description ? (
                        <span className="mt-1 line-clamp-2 block text-xs text-muted-foreground">
                          {item.description}
                        </span>
                      ) : null}
                    </span>
                    <Badge variant="outline" className="shrink-0 text-[10px]">
                      {(item.streams?.length ?? 0) > 0
                        ? c.catalog.data_sync_supported
                        : c.catalog.data_sync_not_supported}
                    </Badge>
                  </button>
                ))}
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog
        open={Boolean(oauthAppTarget)}
        onOpenChange={(open) => {
          if (!open) {
            closeOAuthAppDialog();
          }
        }}
      >
        <DialogContent data-testid="connector-oauth-app-dialog">
          <DialogHeader>
            <DialogTitle>
              {fmt(c.catalog.oauth_app_dialog_title, {
                name: oauthAppTarget?.display_name ?? '',
              })}
            </DialogTitle>
            <p className="text-sm text-muted-foreground">{c.catalog.oauth_app_dialog_subtitle}</p>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <div className="space-y-1">
                <Label className="text-xs">{c.catalog.oauth_client_id_label}</Label>
                <Input
                  value={oauthClientId}
                  onChange={(e) => setOauthClientId(e.target.value)}
                  className="h-8 text-xs"
                  data-testid="oauth-app-client-id"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">{c.catalog.oauth_client_secret_label}</Label>
                <Input
                  type="password"
                  value={oauthClientSecret}
                  onChange={(e) => setOauthClientSecret(e.target.value)}
                  className="h-8 text-xs"
                  data-testid="oauth-app-client-secret"
                />
                {oauthHasSavedSecret ? (
                  <p className="text-[11px] text-muted-foreground">
                    {c.catalog.oauth_secret_keep_hint}
                  </p>
                ) : null}
              </div>
            </div>
            <div className="space-y-1">
              <Label className="text-xs">{c.catalog.oauth_redirect_label}</Label>
              <p className="break-all font-mono text-[11px] text-muted-foreground">
                {workspaceId ? workspaceConnectorOAuthRedirectUri(workspaceId) : ''}
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button
              onClick={() => void handleSaveOAuthApp()}
              disabled={savingOAuthApp}
              data-testid="save-oauth-app-btn"
            >
              {savingOAuthApp ? c.catalog.saving : c.catalog.oauth_app_save}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Connect Dialog */}
      <Dialog
        open={Boolean(selectedConnector)}
        onOpenChange={(o) => {
          if (!o) closeConnectDialog();
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editingConnection
                ? fmt(c.catalog.dialog_reauthorize_title, {
                    name: selectedConnector?.display_name ?? '',
                    connection: editingConnection.service,
                  })
                : fmt(c.catalog.dialog_title, { name: selectedConnector?.display_name ?? '' })}
            </DialogTitle>
            {resolveConnectScope() === 'end_user' && resolveConnectSubjectId() ? (
              <p className="text-xs text-muted-foreground">
                {fmt(c.catalog.scope_subject_label, { id: resolveConnectSubjectId() })}
              </p>
            ) : null}
            {!editingConnection && pendingConnectScope === 'workspace' ? (
              <p className="text-xs text-muted-foreground">{c.catalog.scope_workspace_badge}</p>
            ) : null}
          </DialogHeader>
          <div className="space-y-3 py-2">
            {!hideAuthorizationOAuthDialogFields && selectedConnector ? (
              <div className="space-y-1">
                <Label>{c.mappings.provider_label}</Label>
                <Input value={selectedConnector.service} readOnly disabled />
              </div>
            ) : null}
            {!hideAuthorizationOAuthDialogFields && connectAuthEntriesForDialog.length > 0 ? (
              <div className="space-y-1">
                <Label htmlFor="connector-connect-auth-mode">{c.catalog.auth_mode_label}</Label>
                {showConnectAuthModeSelector ? (
                  <Select value={connAuthMode} onValueChange={handleConnectAuthModeChange}>
                    <SelectTrigger
                      id="connector-connect-auth-mode"
                      data-testid="connector-connect-auth-mode"
                      className="w-full"
                    >
                      <SelectValue placeholder={c.catalog.auth_mode_placeholder} />
                    </SelectTrigger>
                    <SelectContent>
                      {connectAuthEntriesForDialog.map((entry) => (
                        <SelectItem key={entry.auth_mode} value={entry.auth_mode}>
                          {labelForAuthMode(selectedConnector, entry.auth_mode)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : (
                  <p
                    className="text-sm text-foreground"
                    data-testid="connector-connect-auth-mode-locked"
                  >
                    {labelForAuthMode(selectedConnector, connAuthMode)}
                  </p>
                )}
              </div>
            ) : null}
            {connectUsesStructuredFields &&
            (connectAuthEntry?.connection_config?.length ?? 0) > 0 ? (
              <div className="space-y-2">
                <Label>{c.catalog.connection_params_label}</Label>
                <ConnectorConnectAuthFields
                  idPrefix="config"
                  fields={connectAuthEntry!.connection_config!}
                  values={connConfigFieldValues}
                  onChange={(key, value) =>
                    setConnConfigFieldValues((prev) => ({ ...prev, [key]: value }))
                  }
                />
              </div>
            ) : !connectUsesStructuredFields && !oauth2ManifestOnly ? (
              <div className="space-y-1">
                <Label>{c.catalog.config_json_label}</Label>
                <JsonEditor
                  height={120}
                  value={connConfigJson}
                  onChange={setConnConfigJson}
                />
              </div>
            ) : null}
            {oauth2ManifestOnly && editingConnection ? (
              <div
                className="space-y-1 rounded border border-border bg-muted/20 px-3 py-2 text-xs"
                data-testid="connector-edit-oauth-status"
              >
                <p className="font-medium text-foreground">{c.catalog.oauth_edit_status_title}</p>
                <p className="text-muted-foreground">
                  {editingConnection.has_credentials
                    ? c.catalog.oauth_edit_token_saved
                    : c.catalog.oauth_edit_token_missing}
                </p>
                {editingConnection.updated_at ? (
                  <p className="text-muted-foreground">
                    {fmt(c.catalog.edit_updated_at, {
                      time: formatLocaleDateTime(locale as Locale, editingConnection.updated_at),
                    })}
                  </p>
                ) : null}
                {!isAuthorizationConnectFlow ? (
                  <p className="text-muted-foreground">{c.catalog.oauth_edit_manifest_hint}</p>
                ) : null}
              </div>
            ) : null}
            {connectUsesStructuredFields &&
            (connectAuthEntry?.credentials?.length ?? 0) > 0 ? (
              <div className="space-y-2">
                <Label>{c.catalog.credentials_fields_label}</Label>
                <p className="text-xs text-muted-foreground">
                  {editingConnection
                    ? c.catalog.credentials_keep_hint
                    : c.catalog.credentials_fields_hint}
                </p>
                <ConnectorConnectAuthFields
                  idPrefix="cred"
                  fields={connectAuthEntry!.credentials!}
                  values={connCredFieldValues}
                  onChange={(key, value) =>
                    setConnCredFieldValues((prev) => ({ ...prev, [key]: value }))
                  }
                />
              </div>
            ) : !connectUsesStructuredFields && !oauth2ManifestOnly ? (
              <div className="space-y-1">
                <Label>{c.catalog.credentials_json_label}</Label>
                <JsonEditor
                  height={120}
                  value={connCredsJson}
                  onChange={setConnCredsJson}
                />
              </div>
            ) : null}
            {connectAuthEntry && hasStructuredAuthForm(connectAuthEntry) ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-8 px-0 text-xs text-muted-foreground"
                onClick={() => {
                  setConnectFormUseJson((useJson) => {
                    const next = !useJson;
                    if (next && connectAuthEntry) {
                      setConnConfigJson(
                        formatConnectorConnectJson(
                          buildObjectFromAuthFields(
                            connectAuthEntry.connection_config,
                            connConfigFieldValues,
                          ),
                        ),
                      );
                      setConnCredsJson(
                        formatConnectorConnectJson(
                          buildObjectFromAuthFields(
                            connectAuthEntry.credentials,
                            connCredFieldValues,
                          ),
                        ),
                      );
                    }
                    return next;
                  });
                }}
              >
                {c.catalog.advanced_json_toggle}
              </Button>
            ) : null}
            {connectFormUseJson && connectAuthEntry && hasStructuredAuthForm(connectAuthEntry) ? (
              <>
                <div className="space-y-1">
                  <Label>{c.catalog.config_json_label}</Label>
                  <JsonEditor
                    height={100}
                    value={connConfigJson}
                    onChange={setConnConfigJson}
                  />
                </div>
                <div className="space-y-1">
                  <Label>{c.catalog.credentials_json_label}</Label>
                  <JsonEditor
                    height={100}
                    value={connCredsJson}
                    onChange={setConnCredsJson}
                  />
                </div>
              </>
            ) : null}
            {(connAuthMode === 'oauth2' || connAuthMode === 'oauth2_cc') && (
              <div
                className="space-y-2 rounded border border-border bg-muted/30 p-2.5"
                data-testid="connector-connection-oauth-authorize"
              >
                {isAuthorizationConnectFlow ? (
                  authorizationOAuthBrowserFlow ? (
                    !oauthClientId.trim() || !oauthHasSavedSecret ? (
                      <div className="space-y-2">
                        <p className="text-xs text-muted-foreground">
                          {c.catalog.oauth_app_missing_on_connectors}
                        </p>
                        <Button type="button" size="sm" variant="outline" asChild>
                          <Link
                            to={`${workspaceConnectorHomePath(workspaceId!)}?section=connectors`}
                            onClick={() => closeConnectDialog()}
                          >
                            {c.catalog.oauth_go_configure_app}
                          </Link>
                        </Button>
                      </div>
                    ) : oauthAuthorizeUrlLoading ? (
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <Spinner className="size-4" />
                        {c.catalog.oauth_authorize_url_loading}
                      </div>
                    ) : oauthAuthorizeUrl ? (
                      <p
                        className="break-all font-mono text-[11px] text-muted-foreground"
                        data-testid="connector-oauth-authorize-url"
                      >
                        {oauthAuthorizeUrl}
                      </p>
                    ) : showOAuthAuthorizeUrlFailed ? (
                      <p className="text-xs text-muted-foreground">
                        {c.catalog.oauth_authorize_url_failed}
                      </p>
                    ) : null
                  ) : (
                    <>
                      <p className="text-xs text-muted-foreground">
                        {c.catalog.oauth_authorization_flow_hint}
                      </p>
                      {!oauthClientId.trim() || !oauthHasSavedSecret ? (
                        <div className="space-y-2">
                          <p className="text-xs text-muted-foreground">
                            {c.catalog.oauth_app_missing_on_connectors}
                          </p>
                          <Button type="button" size="sm" variant="outline" asChild>
                            <Link
                              to={`${workspaceConnectorHomePath(workspaceId!)}?section=connectors`}
                              onClick={() => closeConnectDialog()}
                            >
                              {c.catalog.oauth_go_configure_app}
                            </Link>
                          </Button>
                        </div>
                      ) : (
                        <>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => void handleBuildOAuthUrl()}
                            data-testid="build-oauth-url-btn"
                          >
                            {c.catalog.oauth_build_url_button}
                          </Button>
                          {oauthAuthorizeUrl ? (
                            <p className="break-all font-mono text-[11px] text-muted-foreground">
                              {oauthAuthorizeUrl}
                            </p>
                          ) : null}
                        </>
                      )}
                    </>
                  )
                ) : (
                  <div className="space-y-2">
                    <p className="text-xs text-muted-foreground">{c.catalog.oauth_use_authorization_tab}</p>
                    <Button type="button" size="sm" variant="outline" asChild>
                      <Link
                        to={workspaceConnectorsAuthorizationHref(workspaceId!, {
                          service: selectedConnector?.service,
                        })}
                        onClick={() => closeConnectDialog()}
                      >
                        {c.catalog.oauth_go_authorization_tab}
                      </Link>
                    </Button>
                  </div>
                )}
              </div>
            )}
          </div>
          <DialogFooter>
            {authorizationOAuthBrowserFlow ? (
              <Button
                onClick={() => {
                  if (oauthAuthorizeUrl) {
                    window.location.assign(oauthAuthorizeUrl);
                  }
                }}
                disabled={
                  oauthAuthorizeUrlLoading ||
                  !oauthAuthorizeUrl ||
                  !oauthClientId.trim() ||
                  !oauthHasSavedSecret
                }
                data-testid="open-oauth-authorize-btn"
              >
                {oauthAuthorizeUrlLoading
                  ? c.catalog.oauth_authorize_url_loading
                  : c.catalog.oauth_go_authorize_button}
              </Button>
            ) : (
              <Button
                onClick={() => void handleSaveConnection()}
                disabled={savingConn || oauthUserAuthBlockedOnConnectorsTab}
              >
                {savingConn ? c.catalog.saving : c.catalog.save_connection}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {workspaceId ? (
        <ConnectorMappingCreateDialog
          workspaceId={workspaceId}
          open={createMappingOpen}
          onOpenChange={setCreateMappingOpen}
          initialTab={createMappingInitialTab}
          connections={connections}
          connectionsLoading={connectionsLoading}
          onManualContinue={(conn) => goToNewMapping(conn ?? undefined)}
          onApplied={() => void loadMappings()}
        />
      ) : null}

      <AlertDialog
        open={deleteMappingId !== null}
        onOpenChange={(open) => !open && setDeleteMappingId(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{c.mappings.delete_dialog_title}</AlertDialogTitle>
            <AlertDialogDescription>{c.mappings.delete_dialog_description}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{c.mappings.cancel_button}</AlertDialogCancel>
            <AlertDialogAction
              disabled={deletingMappingId !== null}
              onClick={(e) => {
                e.preventDefault();
                if (deleteMappingId) {
                  void handleDeleteMapping(deleteMappingId);
                }
              }}
              data-testid="confirm-delete-mapping-btn"
            >
              {deletingMappingId ? c.mappings.deleting_mapping : c.mappings.delete_confirm}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </ConsolePageLayout>
  );
}
