import { zodResolver } from '@hookform/resolvers/zod';
import { type FormEvent, useCallback, useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { ConfirmAlertDialog } from '@/components/app/shared/console/ConfirmAlertDialog.js';
import { ConsolePageLayout } from '@/components/app/shared/console/index.js';
import { Button } from '@/components/ui/button.js';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog.js';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card.js';
import { Checkbox } from '@/components/ui/checkbox.js';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form.js';
import { Input } from '@/components/ui/input.js';
import {
  NativeSelect,
  NativeSelectOption,
} from '@/components/ui/native-select.js';
import { Label } from '@/components/ui/label.js';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select.js';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table.js';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs.js';
import { useI18n } from '@/i18n/context.js';
import { fmt } from '@/i18n/format.js';
import { GraphOverviewStats } from './components/graph-overview-stats.js';
import { GovernanceSettingsRedirectCard } from './components/governance-settings-redirect-card.js';
import { GraphProjectionPanel } from './components/graph-projection-panel.js';
import { useWorkspaceCatalog } from '@/lib/workspace/context.js';
import { useWorkspaceCapabilities } from '@/lib/workspace/capabilities.js';
import { workspaceMemberRoleLabel, workspaceVisibilityLabel } from '@/modules/settings/lib/settings-labels.js';
import {
  workspaceOpenApiDELETE,
  workspaceOpenApiGET,
  workspaceOpenApiPATCH,
  workspaceOpenApiPOST,
  workspaceOpenApiPUT,
  openApiGET,
} from '@/lib/openapi/client.js';
import { useApiErrorMessage } from '@/lib/errors/use-api-error-message.js';

type Member = {
  user_id: string;
  email: string;
  display_name: string;
  role: string;
};

type UserRow = { id: string; email: string; display_name: string };

type WorkspaceRecord = {
  name: string;
  description: string;
  visibility: string;
  my_role: string;
};

type SearchConfig = {
  chunk_backend: 'sqlite_ledger' | 'postgres_ledger';
  vector_backend: 'sqlite_vec' | 'pgvector';
  embedding_model_id: string | null;
  keyword_enabled: boolean;
  semantic_enabled: boolean;
  default_mode: 'keyword' | 'semantic' | 'hybrid';
  auto_index: boolean;
};

type SearchConfigResponse = {
  config: SearchConfig;
  status: {
    storage_ready: boolean;
    keyword_ready: boolean;
    vector_state: 'disabled' | 'not_indexed' | 'stale' | 'ready';
    embedding_configured: boolean;
    model_ref?: string | null;
    dimension?: number | null;
  };
  available: {
    chunk_backends: SearchConfig['chunk_backend'][];
    vector_backends: SearchConfig['vector_backend'][];
    embedding_models: Array<{
      id: string;
      display_name: string;
      model: string;
      enabled: boolean;
    }>;
  };
};

export function WorkspaceSettingsPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { t } = useI18n();
  const emptyCell = t.core.common.emptyCell;
  const ks = t.settings.panel;

  function defaultModeLabel(mode: SearchConfig['default_mode']): string {
    if (mode === 'keyword') return ks.mode_keyword;
    if (mode === 'semantic') return ks.mode_semantic;
    return ks.mode_hybrid;
  }

  function vectorStateLabel(state: SearchConfigResponse['status']['vector_state']): string {
    return ks.vector_state[state] ?? state;
  }
  const apiError = useApiErrorMessage();
  const { getWorkspace, refresh: refreshWorkspaces } = useWorkspaceCatalog();
  const { caps } = useWorkspaceCapabilities();
  const tab = searchParams.get('tab') ?? 'general';

  const [workspace, setWorkspace] = useState<WorkspaceRecord | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [targetUser, setTargetUser] = useState('');
  const [role, setRole] = useState('viewer');
  const [error, setError] = useState<string | null>(null);
  const [searchConfig, setSearchConfig] = useState<SearchConfigResponse | null>(null);
  const [reindexing, setReindexing] = useState(false);
  const [generalEditOpen, setGeneralEditOpen] = useState(false);

  const generalFormSchema = z.object({
    name: z.string().min(1),
    description: z.string(),
    visibility: z.enum(['restricted', 'open']),
  });

  type GeneralFormValues = z.infer<typeof generalFormSchema>;

  const generalForm = useForm<GeneralFormValues>({
    resolver: zodResolver(generalFormSchema),
    defaultValues: { name: '', description: '', visibility: 'restricted' },
  });
  const [searchEditOpen, setSearchEditOpen] = useState(false);
  const [memberAddOpen, setMemberAddOpen] = useState(false);
  const [addingMember, setAddingMember] = useState(false);
  const [resetOpen, setResetOpen] = useState(false);
  const [resetConfirm, setResetConfirm] = useState('');
  const [resetPreview, setResetPreview] = useState<Record<string, number> | null>(null);
  const [resetPreviewLoading, setResetPreviewLoading] = useState(false);
  const [resetScopes, setResetScopes] = useState<string[]>([]);
  const [resetExportPath, setResetExportPath] = useState<string | null>(null);

  const RESET_SCOPE_ORDER = [
    'knowledge',
    'graph',
    'connectors',
    'reasoning',
    'governance',
  ] as const;

  const resetScopeLabel = (scope: string) => {
    const key = `reset_workspace_scope_${scope}` as keyof typeof t.settings.tabs;
    const label = t.settings.tabs[key];
    return typeof label === 'string' ? label : scope;
  };

  function toggleResetScope(scope: string, checked: boolean) {
    setResetScopes((current) => {
      const next = new Set(current);
      if (checked) {
        next.add(scope);
        if (scope === 'knowledge') next.add('graph');
      } else {
        next.delete(scope);
      }
      return RESET_SCOPE_ORDER.filter((s) => next.has(s));
    });
  }
  const [resetting, setResetting] = useState(false);

  const catalogWorkspace = id ? getWorkspace(id) : undefined;
  const name = catalogWorkspace?.name ?? workspace?.name ?? id ?? t.core.common.ellipsis;

  useEffect(() => {
    if (!id) return;
    Promise.all([
      workspaceOpenApiGET<WorkspaceRecord>(id, ''),
      workspaceOpenApiGET<{ members: Member[] }>(id, 'members'),
      openApiGET<{ users: UserRow[] }>('/api/v1/users'),
      workspaceOpenApiGET<SearchConfigResponse>(id, 'search/config'),
    ])
      .then(([workspaceBody, membersBody, usersBody, searchBody]) => {
        setWorkspace(workspaceBody);
        setMembers(membersBody.members);
        setUsers(usersBody.users);
        setSearchConfig(searchBody);
      })
      .catch((err) => setError(apiError(err)));
  }, [apiError, id]);

  useEffect(() => {
    if (generalEditOpen && workspace) {
      generalForm.reset({
        name: workspace.name,
        description: workspace.description,
        visibility: workspace.visibility === 'open' ? 'open' : 'restricted',
      });
    }
  }, [generalEditOpen, workspace, generalForm]);

  async function saveGeneral(values: GeneralFormValues) {
    if (!id) return;
    setError(null);
    try {
      const body = await workspaceOpenApiPATCH<WorkspaceRecord>(id, '', {
        body: {
          name: values.name,
          description: values.description,
          visibility: values.visibility,
        },
      });
      setWorkspace(body);
      await refreshWorkspaces();
      setGeneralEditOpen(false);
    } catch (err) {
      setError(apiError(err));
    }
  }

  async function addMember() {
    if (!id || !targetUser || !workspace) return;
    setAddingMember(true);
    setError(null);
    try {
      await workspaceOpenApiPUT(id, `members/${targetUser}`, { body: { role } });
      const body = await workspaceOpenApiGET<{ members: Member[] }>(id, 'members');
      setMembers(body.members);
      setMemberAddOpen(false);
      setTargetUser('');
      setRole('viewer');
    } catch (err) {
      setError(apiError(err));
    } finally {
      setAddingMember(false);
    }
  }

  async function deleteWorkspace() {
    if (!id) return;
    setError(null);
    try {
      await workspaceOpenApiDELETE(id, '');
      await refreshWorkspaces();
      toast.success(t.core.common.deleteSuccess);
      navigate('/workspaces');
    } catch (err) {
      toast.error(apiError(err));
    }
  }

  const loadResetPreview = useCallback(async () => {
    if (!id) return;
    setResetPreviewLoading(true);
    setResetPreview(null);
    try {
      const body = await workspaceOpenApiGET<{
        counts: Record<string, number>;
        default_scopes?: string[];
        export_pack_path?: string;
      }>(id, 'reset');
      setResetPreview(body.counts);
      setResetScopes(body.default_scopes ?? ['connectors', 'graph', 'knowledge', 'reasoning']);
      setResetExportPath(body.export_pack_path ?? null);
    } catch (err) {
      toast.error(apiError(err));
      setResetOpen(false);
    } finally {
      setResetPreviewLoading(false);
    }
  }, [apiError, id]);

  useEffect(() => {
    if (!resetOpen) {
      setResetConfirm('');
      setResetPreview(null);
      setResetScopes([]);
      setResetExportPath(null);
      return;
    }
    void loadResetPreview();
  }, [loadResetPreview, resetOpen]);

  async function resetWorkspace() {
    if (!id || !workspace) return;
    if (resetScopes.length === 0) {
      toast.error(t.settings.tabs.reset_workspace_scopes_label);
      return;
    }
    if (resetConfirm !== workspace.name) {
      toast.error(t.settings.tabs.reset_workspace_confirm_label);
      return;
    }
    setResetting(true);
    setError(null);
    try {
      const accepted = await workspaceOpenApiPOST<{
        accepted?: boolean;
        job_id?: string;
        ok?: boolean;
      }>(id, 'reset', {
        body: { confirmation: resetConfirm, async: true, scopes: resetScopes },
      });
      if (accepted.accepted && accepted.job_id) {
        for (let i = 0; i < 120; i += 1) {
          const job = await workspaceOpenApiGET<{ job: { status: string } }>(
            id,
            `ingest/jobs/${accepted.job_id}`,
          );
          const status = job.job.status;
          if (status === 'succeeded' || status === 'failed') break;
          await new Promise((r) => setTimeout(r, 500));
        }
      }
      const body = await workspaceOpenApiGET<WorkspaceRecord>(id, '');
      setWorkspace(body);
      setResetOpen(false);
      toast.success(t.settings.tabs.reset_workspace);
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setResetting(false);
    }
  }

  async function saveSearchConfig(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!id || !searchConfig) return;
    setError(null);
    try {
      const body = await workspaceOpenApiPUT<{
        config: SearchConfig;
        status: SearchConfigResponse['status'];
        reindex_required: boolean;
      }>(id, 'search/config', {
        body: {
          chunk_backend: searchConfig.config.chunk_backend,
          vector_backend: searchConfig.config.vector_backend,
          embedding_model_id: searchConfig.config.embedding_model_id,
          keyword_enabled: searchConfig.config.keyword_enabled,
          semantic_enabled: searchConfig.config.semantic_enabled,
          default_mode: searchConfig.config.default_mode,
          auto_index: searchConfig.config.auto_index,
        },
      });
      setSearchConfig((current) =>
        current
          ? { ...current, config: body.config, status: body.status }
          : current,
      );
      toast.success(
        body.reindex_required ? ks.toast_search_saved_reindex : ks.toast_search_saved,
      );
      setSearchEditOpen(false);
    } catch (err) {
      setError(apiError(err));
    }
  }

  async function reindexSearch() {
    if (!id) return;
    setReindexing(true);
    setError(null);
    try {
      await workspaceOpenApiPOST(id, 'search/reindex', { body: {} });
      const current = await workspaceOpenApiGET<SearchConfigResponse>(id, 'search/config');
      setSearchConfig(current);
      toast.success(ks.toast_reindex_done);
    } catch (err) {
      setError(apiError(err));
    } finally {
      setReindexing(false);
    }
  }

  if (!workspace) return <p className="text-sm text-muted-foreground">{t.core.common.loading}</p>;

  const canManageMembers = ['owner', 'admin'].includes(workspace.my_role);
  const canEditGeneral = ['owner', 'admin'].includes(workspace.my_role);
  const canEditSearch = ['owner', 'admin'].includes(workspace.my_role);
  const canRebuildGraph = caps?.graph_write === true;
  const graphEnabled = caps?.graph === true;

  return (
    <ConsolePageLayout
      crumbs={[
        { label: t.core.workspace_nav.platform.workspaces, to: '/workspaces' },
        { label: name, to: id ? `/workspaces/${id}/graph` : '/workspaces' },
        { label: t.settings.menu.settings },
      ]}
      subtitle={t.settings.page.subtitle}
      meta={fmt(ks.my_role_meta, { role: workspaceMemberRoleLabel(ks, workspace.my_role) })}
    >
      {error && <p className="text-sm text-destructive">{error}</p>}

      <Tabs
        value={tab}
        onValueChange={(value) => setSearchParams({ tab: value }, { replace: true })}
      >
        <TabsList>
          <TabsTrigger value="general">{t.settings.tabs.general}</TabsTrigger>
          <TabsTrigger value="search">{t.settings.tabs.search}</TabsTrigger>
          <TabsTrigger value="graph">
            {graphEnabled ? t.settings.tabs.graph_projection : ks.graph_runtime_short}
          </TabsTrigger>
          <TabsTrigger value="members">{t.settings.tabs.members}</TabsTrigger>
          <TabsTrigger value="danger">{t.settings.tabs.danger}</TabsTrigger>
        </TabsList>

        <TabsContent value="general" className="mt-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0">
              <CardTitle className="text-base">{t.settings.tabs.general}</CardTitle>
              {canEditGeneral ? (
                <Button type="button" size="sm" variant="outline" onClick={() => setGeneralEditOpen(true)}>
                  {ks.edit}
                </Button>
              ) : null}
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <p>
                <span className="text-muted-foreground">{ks.fields.name}{ks.label_suffix}</span>
                {workspace.name}
              </p>
              <p>
                <span className="text-muted-foreground">{ks.fields.description}{ks.label_suffix}</span>
                {workspace.description || emptyCell}
              </p>
              <p>
                <span className="text-muted-foreground">{ks.fields.visibility}{ks.label_suffix}</span>
                {workspaceVisibilityLabel(ks, workspace.visibility)}
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="graph" className="mt-4 space-y-4">
          {id ? (
            <>
              <GraphOverviewStats workspaceId={id} />
              <GraphProjectionPanel
                workspaceId={id}
                canRebuild={canRebuildGraph}
                graphEnabled={graphEnabled}
              />
              <GovernanceSettingsRedirectCard workspaceId={id} />
            </>
          ) : null}
        </TabsContent>

        <TabsContent value="search" className="mt-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0">
              <CardTitle className="text-base">{t.settings.tabs.search}</CardTitle>
              {canEditSearch && searchConfig ? (
                <Button type="button" size="sm" variant="outline" onClick={() => setSearchEditOpen(true)}>
                  {ks.configure_search}
                </Button>
              ) : null}
            </CardHeader>
            <CardContent>
              {!searchConfig ? (
                <p className="text-sm text-muted-foreground">{t.core.common.loading}</p>
              ) : (
                <div className="space-y-4 text-sm">
                  <p>
                    <span className="text-muted-foreground">{ks.vector_store}{ks.label_suffix}</span>
                    {searchConfig.config.vector_backend === 'pgvector'
                      ? 'PostgreSQL (pgvector)'
                      : 'SQLite (sqlite-vec)'}
                  </p>
                  <p>
                    <span className="text-muted-foreground">{ks.embedding_model}{ks.label_suffix}</span>
                    {searchConfig.config.embedding_model_id ?? ks.platform_default_embedding}
                  </p>
                  <p>
                    <span className="text-muted-foreground">{ks.default_mode}{ks.label_suffix}</span>
                    {defaultModeLabel(searchConfig.config.default_mode)}
                  </p>
                  <div className="rounded-md border p-3">
                    <div>
                      {ks.status_storage}{ks.label_suffix}
                      {searchConfig.status.storage_ready ? ks.storage_ready : ks.storage_not_ready}
                    </div>
                    <div>
                      {ks.status_vector_index}{ks.label_suffix}
                      {vectorStateLabel(searchConfig.status.vector_state)}
                    </div>
                    <div>
                      {ks.status_embedding}{ks.label_suffix}
                      {searchConfig.status.embedding_configured
                        ? ks.embedding_configured
                        : ks.embedding_fallback}
                    </div>
                  </div>
                  {canEditSearch ? (
                    <Button
                      type="button"
                      variant="outline"
                      onClick={reindexSearch}
                      disabled={reindexing || !searchConfig.config.semantic_enabled}
                    >
                      {reindexing ? ks.reindexing : ks.reindex_vector}
                    </Button>
                  ) : null}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="members" className="mt-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0">
              <CardTitle className="text-base">{t.settings.tabs.members}</CardTitle>
              {canManageMembers ? (
                <Button type="button" size="sm" onClick={() => setMemberAddOpen(true)}>
                  {ks.add_member}
                </Button>
              ) : null}
            </CardHeader>
            <CardContent className="space-y-4">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{ks.col_user}</TableHead>
                    <TableHead>{ks.col_email}</TableHead>
                    <TableHead>{ks.col_role}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {members.map((m) => (
                    <TableRow key={m.user_id}>
                      <TableCell>{m.display_name}</TableCell>
                      <TableCell>{m.email}</TableCell>
                      <TableCell>{workspaceMemberRoleLabel(ks, m.role)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="danger" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">{t.settings.tabs.danger}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              {workspace.my_role === 'owner' && (
                <>
                  <p className="text-sm text-muted-foreground">{t.settings.tabs.reset_workspace_desc}</p>
                  <Button type="button" variant="outline" onClick={() => setResetOpen(true)}>
                    {t.settings.tabs.reset_workspace}
                  </Button>
                </>
              )}
              {(workspace.my_role === 'owner' || workspace.my_role === 'admin') && (
                <ConfirmAlertDialog
                  title={t.settings.tabs.delete_workspace}
                  description={t.settings.tabs.delete_confirm}
                  destructive
                  onConfirm={() => deleteWorkspace()}
                  trigger={
                    <Button type="button" variant="destructive">
                      {t.settings.tabs.delete_workspace}
                    </Button>
                  }
                />
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog open={generalEditOpen} onOpenChange={setGeneralEditOpen}>
        <DialogContent className="sm:max-w-md">
          <Form {...generalForm}>
            <form className="space-y-4" onSubmit={generalForm.handleSubmit(saveGeneral)}>
              <DialogHeader>
                <DialogTitle>{t.settings.tabs.general}</DialogTitle>
                <DialogDescription>{ks.general_edit_desc}</DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-2">
                <FormField
                  control={generalForm.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{ks.fields.name}</FormLabel>
                      <FormControl>
                        <Input {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={generalForm.control}
                  name="description"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{ks.fields.description}</FormLabel>
                      <FormControl>
                        <Input {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={generalForm.control}
                  name="visibility"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{ks.fields.visibility}</FormLabel>
                      <FormControl>
                        <div className="native-select--full">
                          <NativeSelect value={field.value} onChange={field.onChange}>
                            <NativeSelectOption value="restricted">
                              {ks.visibility_labels.restricted}
                            </NativeSelectOption>
                            <NativeSelectOption value="open">{ks.visibility_labels.open}</NativeSelectOption>
                          </NativeSelect>
                        </div>
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setGeneralEditOpen(false)}>
                  {t.core.common.cancel}
                </Button>
                <Button type="submit">{t.core.common.save}</Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      <Dialog open={resetOpen} onOpenChange={setResetOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{t.settings.tabs.reset_workspace}</DialogTitle>
            <DialogDescription>{t.settings.tabs.reset_workspace_desc}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            {resetPreviewLoading ? (
              <p className="text-sm text-muted-foreground">
                {t.settings.tabs.reset_workspace_preview_loading}
              </p>
            ) : resetPreview ? (
              <p className="text-sm text-muted-foreground">
                {fmt(t.settings.tabs.reset_workspace_preview, {
                  documents: String(resetPreview.document_count ?? 0),
                  entities: String(resetPreview.entity_count ?? 0),
                  statements: String(resetPreview.statement_count ?? 0),
                  chunks: String(resetPreview.chunk_count ?? 0),
                })}
              </p>
            ) : null}
            {resetExportPath ? (
              <p className="text-sm text-muted-foreground">
                {t.settings.tabs.reset_workspace_export_before}{' '}
                <Link
                  to={resetExportPath}
                  className="text-foreground underline underline-offset-4"
                  onClick={() => setResetOpen(false)}
                >
                  {t.settings.tabs.reset_workspace_export_link}
                </Link>
              </p>
            ) : null}
            <div className="space-y-2">
              <Label>{t.settings.tabs.reset_workspace_scopes_label}</Label>
              <div className="space-y-2 rounded-md border p-3">
                {RESET_SCOPE_ORDER.map((scope) => (
                  <label key={scope} className="flex items-start gap-2 text-sm">
                    <Checkbox
                      checked={resetScopes.includes(scope)}
                      onCheckedChange={(value) => toggleResetScope(scope, value === true)}
                    />
                    <span>{resetScopeLabel(scope)}</span>
                  </label>
                ))}
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="workspace-reset-confirm">
                {t.settings.tabs.reset_workspace_confirm_label}
              </Label>
              <Input
                id="workspace-reset-confirm"
                value={resetConfirm}
                onChange={(event) => setResetConfirm(event.target.value)}
                autoComplete="off"
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setResetOpen(false)}>
              {t.core.common.cancel}
            </Button>
            <Button
              type="button"
              variant="destructive"
              disabled={
                resetting || resetConfirm !== workspace?.name || resetScopes.length === 0
              }
              onClick={() => void resetWorkspace()}
            >
              {t.settings.tabs.reset_workspace}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {searchConfig ? (
        <Dialog open={searchEditOpen} onOpenChange={setSearchEditOpen}>
          <DialogContent className="sm:max-w-lg">
            <form className="space-y-5" onSubmit={saveSearchConfig}>
              <DialogHeader>
                <DialogTitle>{t.settings.tabs.search}</DialogTitle>
                <DialogDescription>{ks.search_edit_desc}</DialogDescription>
              </DialogHeader>
              <div className="max-h-[min(60vh,24rem)] space-y-5 overflow-y-auto py-2">
                <div className="space-y-2">
                  <Label>{ks.vector_store}</Label>
                  <Select
                    value={searchConfig.config.vector_backend}
                    onValueChange={(value: SearchConfig['vector_backend']) =>
                      setSearchConfig((current) =>
                        current
                          ? {
                              ...current,
                              config: { ...current.config, vector_backend: value },
                            }
                          : current,
                      )
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {searchConfig.available.vector_backends.map((backend) => (
                        <SelectItem key={backend} value={backend}>
                          {backend === 'pgvector'
                            ? 'PostgreSQL (pgvector)'
                            : 'SQLite (sqlite-vec)'}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>{ks.embedding_model}</Label>
                  <Select
                    value={searchConfig.config.embedding_model_id ?? '__default__'}
                    onValueChange={(value) =>
                      setSearchConfig((current) =>
                        current
                          ? {
                              ...current,
                              config: {
                                ...current.config,
                                embedding_model_id: value === '__default__' ? null : value,
                              },
                            }
                          : current,
                      )
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__default__">{ks.default_embedding_option}</SelectItem>
                      {searchConfig.available.embedding_models
                        .filter((model) => model.enabled)
                        .map((model) => (
                          <SelectItem key={model.id} value={model.id}>
                            {model.display_name || model.model}
                          </SelectItem>
                        ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="flex items-center gap-2">
                    <Checkbox
                      id="search-keyword-enabled"
                      checked={searchConfig.config.keyword_enabled}
                      onCheckedChange={(checked) =>
                        setSearchConfig((current) =>
                          current
                            ? {
                                ...current,
                                config: {
                                  ...current.config,
                                  keyword_enabled: checked === true,
                                },
                              }
                            : current,
                        )
                      }
                    />
                    <Label htmlFor="search-keyword-enabled" className="cursor-pointer font-normal">
                      {ks.keyword_search}
                    </Label>
                  </div>
                  <div className="flex items-center gap-2">
                    <Checkbox
                      id="search-semantic-enabled"
                      checked={searchConfig.config.semantic_enabled}
                      onCheckedChange={(checked) =>
                        setSearchConfig((current) =>
                          current
                            ? {
                                ...current,
                                config: {
                                  ...current.config,
                                  semantic_enabled: checked === true,
                                },
                              }
                            : current,
                        )
                      }
                    />
                    <Label htmlFor="search-semantic-enabled" className="cursor-pointer font-normal">
                      {ks.semantic_search}
                    </Label>
                  </div>
                  <div className="flex items-center gap-2 sm:col-span-2">
                    <Checkbox
                      id="search-auto-index"
                      checked={searchConfig.config.auto_index}
                      onCheckedChange={(checked) =>
                        setSearchConfig((current) =>
                          current
                            ? {
                                ...current,
                                config: {
                                  ...current.config,
                                  auto_index: checked === true,
                                },
                              }
                            : current,
                        )
                      }
                    />
                    <Label htmlFor="search-auto-index" className="cursor-pointer font-normal">
                      {ks.auto_index_on_upload}
                    </Label>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>{ks.default_search_mode}</Label>
                  <Select
                    value={searchConfig.config.default_mode}
                    onValueChange={(value: SearchConfig['default_mode']) =>
                      setSearchConfig((current) =>
                        current
                          ? {
                              ...current,
                              config: { ...current.config, default_mode: value },
                            }
                          : current,
                      )
                    }
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="keyword">{ks.mode_keyword}</SelectItem>
                      <SelectItem value="semantic">{ks.mode_semantic}</SelectItem>
                      <SelectItem value="hybrid">{ks.mode_hybrid}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setSearchEditOpen(false)}>
                  {t.core.common.cancel}
                </Button>
                <Button type="submit">{t.core.common.save}</Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      ) : null}

      <Dialog open={memberAddOpen} onOpenChange={setMemberAddOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{ks.add_member_title}</DialogTitle>
            <DialogDescription>{ks.add_member_desc}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="space-y-2">
              <Label>{ks.col_user}</Label>
              <Select value={targetUser} onValueChange={setTargetUser}>
                <SelectTrigger>
                  <SelectValue placeholder={ks.select_user} />
                </SelectTrigger>
                <SelectContent>
                  {users.map((u) => (
                    <SelectItem key={u.id} value={u.id}>
                      {u.display_name} ({u.email})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>{ks.role}</Label>
              <Select value={role} onValueChange={setRole}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="viewer">{ks.role_labels.viewer}</SelectItem>
                  <SelectItem value="editor">{ks.role_labels.editor}</SelectItem>
                  <SelectItem value="admin">{ks.role_labels.admin}</SelectItem>
                  <SelectItem value="owner">{ks.role_labels.owner}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setMemberAddOpen(false)}>
              {t.core.common.cancel}
            </Button>
            <Button type="button" disabled={!targetUser || addingMember} onClick={() => void addMember()}>
              {addingMember ? t.core.common.processing : t.core.common.save}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ConsolePageLayout>
  );
}
