import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { PlaygroundConnectAuthFields } from '@/modules/workspace/integration/components/playground-connect-auth-fields.js';
import {
  authModeDisplayLabel,
  connectorAuthCatalogEntries,
  findAuthCatalogEntry,
} from '@/modules/workspace/integration/lib/playground-auth-display.js';
import {
  authFieldDefaultValues,
  buildObjectFromAuthFields,
  hasStructuredAuthForm,
  type PlaygroundAuthCatalogEntry,
} from '@/modules/workspace/integration/lib/playground-auth-fields.js';
import {
  connectorAuthNeedsPkce,
  generatePkcePair,
  savePlaygroundPendingOAuth,
  workspacePlaygroundOAuthRedirectUri,
} from '@/modules/workspace/integration/lib/playground-oauth.js';
import {
  DataPanel,
  DataPanelBody,
  DataPanelHeader,
} from '@/components/app/shared/console/index.js';
import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';
import { Badge } from '@/components/ui/badge.js';
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
import { useI18n } from '@/i18n/context.js';
import { fmt } from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import { formatUserFacingApiError } from '@/lib/errors/api-error-message.js';
import {
  workspaceOpenApiDELETE,
  workspaceOpenApiGET,
  workspaceOpenApiPOST,
  workspaceOpenApiPUT,
} from '@/lib/openapi/client.js';
import {
  defaultPlaygroundSubjectId,
  readPlaygroundSubjectId,
  writePlaygroundSubjectId,
} from '@/modules/workspace/integration/lib/playground-subject.js';
import { resourceCardSurfaceClass } from '@/lib/ui-classes/card-surface.js';
import { cn } from '@/lib/utils.js';

function providerDisplayName(provider: IntegrationProvider): string {
  const name = provider.display_name;
  if (typeof name === 'string' && name.trim()) {
    return name.trim();
  }
  return provider.service;
}

function providerDescription(provider: IntegrationProvider): string {
  const desc = provider.description;
  if (typeof desc === 'string' && desc.trim()) {
    return desc.trim();
  }
  return provider.service;
}

type IntegrationProvider = {
  service: string;
  display_name?: string | null;
  description?: string | null;
  auth?: PlaygroundAuthCatalogEntry[];
  streams?: Array<{ name: string; display_name?: string }>;
  tools?: Array<{ id: string; name?: string }>;
};

type PlaygroundConnection = {
  service: string;
    auth_type: string;
  connection_scope?: string;
  subject_id?: string;
  has_credentials?: boolean;
  updated_at?: string;
};

type ConnectorsPlaygroundPanelProps = {
  workspaceId: string;
};

export function ConnectorsPlaygroundPanel({ workspaceId }: ConnectorsPlaygroundPanelProps) {
  const { t, locale } = useI18n();
  const [searchParams] = useSearchParams();
  const p = t.integration.connectors_playground;
  const authModeLabels = t.connectors.page.catalog.auth_modes;
  const serviceDeepLinkHandled = useRef(false);

  const initialSubjectFromUrl = searchParams.get('subject_id')?.trim();
  const [subjectDraft, setSubjectDraft] = useState(() =>
    initialSubjectFromUrl || readPlaygroundSubjectId(workspaceId),
  );
  const [subjectId, setSubjectId] = useState(() =>
    initialSubjectFromUrl || readPlaygroundSubjectId(workspaceId),
  );
  const [providers, setProviders] = useState<IntegrationProvider[]>([]);
  const [connections, setConnections] = useState<PlaygroundConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [connectOpen, setConnectOpen] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<IntegrationProvider | null>(null);
  const [authMode, setAuthMode] = useState('custom');
  const [configValues, setConfigValues] = useState<Record<string, string>>({});
  const [credValues, setCredValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [checkingService, setCheckingService] = useState<string | null>(null);
  const [oauthAuthorizeUrl, setOauthAuthorizeUrl] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  const catalog = t.connectors.page.catalog;

  const connectionByService = useMemo(() => {
    const map = new Map<string, PlaygroundConnection>();
    for (const conn of connections) {
      map.set(conn.service, conn);
    }
    return map;
  }, [connections]);

  const filteredProviders = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return providers;
    return providers.filter((item) => {
      const name = (item.display_name ?? item.service).toLowerCase();
      return name.includes(q) || item.service.toLowerCase().includes(q);
    });
  }, [providers, searchQuery]);

  const authEntry = useMemo(
    () =>
      selectedProvider
        ? findAuthCatalogEntry(selectedProvider.auth, authMode)
        : undefined,
    [selectedProvider, authMode],
  );

  const mcpExample = useMemo(
    () =>
      JSON.stringify(
        {
          name: 'list_connector_connections',
          arguments: {
            connection_scope: 'end_user',
            subject_id: subjectId,
          },
        },
        null,
        2,
      ),
    [subjectId],
  );

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [provRes, connRes] = await Promise.all([
        workspaceOpenApiGET<{ providers: IntegrationProvider[] }>(
          workspaceId,
          'connectors/embed/providers',
          { params: { query: { limit: 100 } } },
        ),
        workspaceOpenApiGET<{ connections: PlaygroundConnection[] }>(
          workspaceId,
          'connectors/embed/connections',
          { params: { query: { subject_id: subjectId } } },
        ),
      ]);
      setProviders(provRes.providers ?? []);
      setConnections(connRes.connections ?? []);
    } catch (err) {
      toast.error(formatUserFacingApiError(err, locale as Locale));
    } finally {
      setLoading(false);
    }
  }, [workspaceId, subjectId, locale]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    const fromUrl = searchParams.get('subject_id')?.trim();
    if (!fromUrl) {
      return;
    }
    writePlaygroundSubjectId(workspaceId, fromUrl);
    setSubjectId(fromUrl);
    setSubjectDraft(fromUrl);
  }, [workspaceId, searchParams]);

  useEffect(() => {
    if (serviceDeepLinkHandled.current || loading) {
      return;
    }
    const service = searchParams.get('service')?.trim();
    if (!service) {
      return;
    }
    const provider = providers.find((item) => item.service === service);
    if (!provider) {
      return;
    }
    serviceDeepLinkHandled.current = true;
    openConnect(provider);
  }, [loading, providers, searchParams]);

  function applySubject() {
    const next = subjectDraft.trim() || defaultPlaygroundSubjectId(workspaceId);
    writePlaygroundSubjectId(workspaceId, next);
    setSubjectId(next);
    setSubjectDraft(next);
  }

  function openConnect(provider: IntegrationProvider) {
    const modes = connectorAuthCatalogEntries(provider.auth);
    const initialMode = modes[0]?.auth_mode ?? 'custom';
    const entry = findAuthCatalogEntry(provider.auth, initialMode);
    setSelectedProvider(provider);
    setAuthMode(initialMode);
    setConfigValues(authFieldDefaultValues(entry?.connection_config));
    setCredValues(authFieldDefaultValues(entry?.credentials));
    setOauthAuthorizeUrl(null);
    setConnectOpen(true);
  }

  function onAuthModeChange(mode: string) {
    if (!selectedProvider) return;
    const entry = findAuthCatalogEntry(selectedProvider.auth, mode);
    setAuthMode(mode);
    setConfigValues(authFieldDefaultValues(entry?.connection_config));
    setCredValues(authFieldDefaultValues(entry?.credentials));
    setOauthAuthorizeUrl(null);
  }

  async function saveConnection() {
    if (!selectedProvider) return;
    setSaving(true);
    try {
      const entry = findAuthCatalogEntry(selectedProvider.auth, authMode);
      const connection_config = hasStructuredAuthForm(entry)
        ? buildObjectFromAuthFields(entry?.connection_config, configValues)
        : {};
      const credentials = hasStructuredAuthForm(entry)
        ? buildObjectFromAuthFields(entry?.credentials, credValues)
        : {};
      await workspaceOpenApiPUT<{ connection: PlaygroundConnection }>(
        workspaceId,
        `connectors/embed/connections/${selectedProvider.service}`,
        {
          body: {
            subject_id: subjectId,
            auth_type: authMode,
            connection_config,
            credentials,
          },
        },
      );
      toast.success(p.save_success);
      setConnectOpen(false);
      await loadData();
    } catch (err) {
      toast.error(formatUserFacingApiError(err, locale as Locale));
    } finally {
      setSaving(false);
    }
  }

  async function startOAuth() {
    if (!selectedProvider) return;
    const entry = findAuthCatalogEntry(selectedProvider.auth, authMode);
    const cfg = hasStructuredAuthForm(entry)
      ? buildObjectFromAuthFields(entry?.connection_config, configValues)
      : {};
    const redirectUri = workspacePlaygroundOAuthRedirectUri(workspaceId);
    let codeChallenge: string | undefined;
    let codeVerifier: string | undefined;
    if (connectorAuthNeedsPkce(selectedProvider.auth)) {
      const pkce = await generatePkcePair();
      codeVerifier = pkce.verifier;
      codeChallenge = pkce.challenge;
    }
    try {
      const res = await workspaceOpenApiPOST<{ authorize_url: string; state: string }>(
        workspaceId,
        `connectors/embed/oauth/${selectedProvider.service}/authorize-url`,
        {
          body: {
            subject_id: subjectId,
            redirect_uri: redirectUri,
            connection_config: cfg,
            code_challenge: codeChallenge ?? null,
          },
        },
      );
      savePlaygroundPendingOAuth({
        workspaceId,
        service: selectedProvider.service,
                connectionConfig: cfg,
        state: res.state,
        redirectUri,
        codeVerifier,
        endUserSubjectId: subjectId,
        returnTo: 'integration-connectors',
      });
      setOauthAuthorizeUrl(res.authorize_url);
      toast.success(t.connectors.page.catalog.oauth_url_generated);
    } catch (err) {
      toast.error(formatUserFacingApiError(err, locale as Locale));
    }
  }

  async function checkConnection(service: string) {
    setCheckingService(service);
    try {
      await workspaceOpenApiPOST(
        workspaceId,
        `connectors/embed/connections/${service}/check`,
        { params: { query: { subject_id: subjectId } } },
      );
      toast.success(p.check_success);
    } catch (err) {
      toast.error(formatUserFacingApiError(err, locale as Locale));
    } finally {
      setCheckingService(null);
    }
  }

  async function deleteConnection(service: string) {
    try {
      await workspaceOpenApiDELETE(workspaceId, 'connectors/embed/connections/' + service, {
        params: { query: { subject_id: subjectId } },
      });
      toast.success(p.delete_success);
      await loadData();
    } catch (err) {
      toast.error(formatUserFacingApiError(err, locale as Locale));
    }
  }

  const isOAuthMode = authMode === 'oauth2' || authMode === 'oauth2_cc';

  return (
    <div className="space-y-4" data-testid="workspace-integration-connectors-playground">
      <DataPanel>
        <DataPanelHeader title={p.subject_panel_title} subtitle={p.hint} />
        <DataPanelBody>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="min-w-0 flex-1 space-y-1">
              <Label htmlFor="playground-subject-id">{p.subject_label}</Label>
              <Input
                id="playground-subject-id"
                value={subjectDraft}
                onChange={(e) => setSubjectDraft(e.target.value)}
                className="font-mono text-sm"
                data-testid="playground-subject-id"
              />
              <p className="text-xs text-muted-foreground">{p.subject_hint}</p>
            </div>
            <Button type="button" variant="secondary" onClick={() => applySubject()}>
              {p.subject_apply}
            </Button>
          </div>
        </DataPanelBody>
      </DataPanel>

      <DataPanel>
        <DataPanelHeader title={p.list_title} subtitle={p.list_subtitle} />
        <DataPanelBody padded={false}>
          <div className="border-b border-border px-4 py-3">
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={p.search_placeholder}
              className="max-w-md"
              data-testid="playground-connectors-search"
            />
          </div>
          {loading ? (
            <p className="px-4 py-8 text-sm text-muted-foreground">{t.core.common.loading}</p>
          ) : filteredProviders.length === 0 ? (
            <p className="px-4 py-8 text-sm text-muted-foreground">{catalog.configured_empty}</p>
          ) : (
            <div className="grid grid-cols-1 gap-3 p-4 md:grid-cols-2 xl:grid-cols-3">
              {filteredProviders.map((provider) => {
                const conn = connectionByService.get(provider.service);
                const connected = Boolean(conn);
                const firstAuthEntry = connectorAuthCatalogEntries(provider.auth)[0];
                const firstAuth = firstAuthEntry.auth_mode;
                const firstAuthLabel = authModeDisplayLabel(
                  firstAuth,
                  firstAuthEntry.display_name,
                  authModeLabels,
                );
                return (
                  <div
                    key={provider.service}
                    className={cn(
                      resourceCardSurfaceClass,
                      'flex flex-col justify-between gap-3 rounded-lg p-3.5',
                    )}
                    data-testid={`playground-provider-card-${provider.service}`}
                  >
                    <div className="min-w-0 space-y-2">
                      <div className="flex items-start justify-between gap-2">
                        <span className="font-medium text-sm text-foreground">
                          {providerDisplayName(provider)}
                        </span>
                        <Badge
                          variant={connected ? 'secondary' : 'outline'}
                          className={cn(
                            'shrink-0 text-[10px]',
                            connected && 'badge-status-success',
                          )}
                          data-testid={
                            connected
                              ? `playground-connector-status-connected-${provider.service}`
                              : undefined
                          }
                        >
                          {connected ? p.status_connected : p.status_not_connected}
                        </Badge>
                      </div>
                      <p className="line-clamp-2 text-xs text-muted-foreground">
                        {providerDescription(provider)}
                      </p>
                      <div className="flex flex-wrap items-center gap-1.5">
                        <Badge variant="secondary" className="text-[10px]">
                          {firstAuthLabel}
                        </Badge>
                        <Badge
                          variant="outline"
                          className={cn(
                            'text-[10px]',
                            (provider.streams?.length ?? 0) > 0 && 'badge-status-success',
                          )}
                        >
                          {(provider.streams?.length ?? 0) > 0
                            ? catalog.data_sync_supported
                            : catalog.data_sync_not_supported}
                        </Badge>
                        {(provider.tools?.length ?? 0) > 0 ? (
                          <span className="text-[11px] text-muted-foreground">
                            {fmt(catalog.tools_badge, {
                              count: provider.tools?.length ?? 0,
                            })}
                          </span>
                        ) : null}
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2 pt-1">
                      {connected ? (
                        <>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            className="flex-1 sm:flex-none"
                            disabled={checkingService === provider.service}
                            onClick={() => void checkConnection(provider.service)}
                          >
                            {checkingService === provider.service
                              ? catalog.checking
                              : catalog.check_button}
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="secondary"
                            onClick={() => openConnect(provider)}
                          >
                            {p.manage}
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            onClick={() => void deleteConnection(provider.service)}
                          >
                            {catalog.delete_button}
                          </Button>
                        </>
                      ) : (
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          className="w-full sm:w-auto"
                          onClick={() => openConnect(provider)}
                          data-testid={`playground-connect-btn-${provider.service}`}
                        >
                          <PublicIcon name="plug-01" size={14} className="mr-1" />
                          {catalog.connect_button}
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </DataPanelBody>
      </DataPanel>

      <details className="rounded-lg border border-border px-4 py-3">
        <summary className="cursor-pointer text-sm font-medium text-foreground">
          {p.mcp_title}
        </summary>
        <p className="mt-2 text-xs text-muted-foreground">{p.mcp_hint}</p>
        <pre className="mt-2 overflow-x-auto rounded-md bg-muted/50 p-3 font-mono text-[11px] leading-relaxed">
          {mcpExample}
        </pre>
      </details>

      <Dialog open={connectOpen} onOpenChange={setConnectOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-md">
          <DialogHeader>
            <DialogTitle>
              {selectedProvider
                ? providerDisplayName(selectedProvider)
                : p.connect}
            </DialogTitle>
          </DialogHeader>
          {selectedProvider ? (
            <div className="space-y-4">
              <div className="space-y-1">
                <Label>{t.connectors.page.catalog.auth_mode_label}</Label>
                <Select value={authMode} onValueChange={onAuthModeChange}>
                  <SelectTrigger>
                    <SelectValue placeholder={t.connectors.page.catalog.auth_mode_placeholder} />
                  </SelectTrigger>
                  <SelectContent>
                    {connectorAuthCatalogEntries(selectedProvider.auth).map((entry) => (
                      <SelectItem key={entry.auth_mode} value={entry.auth_mode}>
                        {authModeDisplayLabel(
                          entry.auth_mode,
                          entry.display_name,
                          authModeLabels,
                        )}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {hasStructuredAuthForm(authEntry) ? (
                <>
                  {authEntry?.connection_config?.length ? (
                    <PlaygroundConnectAuthFields
                      fields={authEntry.connection_config}
                      values={configValues}
                      onChange={(key, value) =>
                        setConfigValues((prev) => ({ ...prev, [key]: value }))
                      }
                      idPrefix="pg-cfg"
                    />
                  ) : null}
                  {authEntry?.credentials?.length ? (
                    <PlaygroundConnectAuthFields
                      fields={authEntry.credentials}
                      values={credValues}
                      onChange={(key, value) =>
                        setCredValues((prev) => ({ ...prev, [key]: value }))
                      }
                      idPrefix="pg-cred"
                    />
                  ) : null}
                </>
              ) : null}
              {isOAuthMode ? (
                <div className="space-y-2">
                  <p className="text-xs text-muted-foreground">{p.oauth_workspace_hint}</p>
                  <p className="text-[11px] text-muted-foreground">{p.oauth_same_window_hint}</p>
                  {oauthAuthorizeUrl ? (
                    <Button
                      type="button"
                      className="w-full"
                      onClick={() => {
                        window.location.assign(oauthAuthorizeUrl);
                      }}
                    >
                      {t.connectors.page.catalog.oauth_open_authorize}
                    </Button>
                  ) : (
                    <Button type="button" variant="secondary" onClick={() => void startOAuth()}>
                      {t.connectors.page.catalog.oauth_build_url_button}
                    </Button>
                  )}
                </div>
              ) : null}
            </div>
          ) : null}
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setConnectOpen(false)}>
              {t.core.common.cancel}
            </Button>
            {!isOAuthMode ? (
              <Button type="button" disabled={saving} onClick={() => void saveConnection()}>
                {saving ? t.core.common.loading : p.save}
              </Button>
            ) : null}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
