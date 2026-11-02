import { useEffect, useMemo, useState } from 'react';
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom';
import { ApiTokenCreateForm } from '@/modules/workspace/integration/components/api-token-create-form.js';
import type {
  HttpOperationEntry,
  McpToolEntry,
} from '@/modules/workspace/integration/components/mcp-integration-panel.js';
import { ConsolePageLayout } from '@/components/app/shared/console/index.js';
import { Button } from '@/components/ui/button.js';
import { useI18n } from '@/i18n/context.js';
import { workspacePath } from '@/lib/nav/nav-config.js';
import { workspaceOpenApiGET } from '@/lib/openapi/client.js';
import { useWorkspaceCatalog } from '@/lib/workspace/context.js';
import { useWorkspaceMcpIntegration } from '@/modules/workspace/integration/lib/use-mcp-integration.js';

const FORM_ID = 'api-token-create-form';

export function IntegrationTokenNewPage() {
  const { id: workspaceId } = useParams();
  const navigate = useNavigate();
  const { t } = useI18n();
  const { getWorkspace } = useWorkspaceCatalog();
  const [myRole, setMyRole] = useState<string | undefined>();
  const [submitting, setSubmitting] = useState(false);

  const canManageTokens = ['owner', 'admin'].includes(myRole ?? getWorkspace(workspaceId ?? '')?.my_role ?? '');
  const integration = useWorkspaceMcpIntegration(workspaceId, canManageTokens);

  useEffect(() => {
    if (!workspaceId) return;
    workspaceOpenApiGET<{ my_role: string }>(workspaceId, '')
      .then((workspace) => setMyRole(workspace.my_role))
      .catch(() => setMyRole(undefined));
  }, [workspaceId]);

  const mcpTools: McpToolEntry[] = useMemo(() => {
    if (integration.mcpInfo?.tool_entries?.length) {
      return integration.mcpInfo.tool_entries;
    }
    return (integration.mcpInfo?.tools ?? []).map((name) => ({
      name,
      description: name,
      access: 'write' as const,
    }));
  }, [integration.mcpInfo]);

  const httpOperations: HttpOperationEntry[] = useMemo(
    () => integration.mcpInfo?.http_operation_entries ?? [],
    [integration.mcpInfo],
  );

  if (!workspaceId) {
    return null;
  }

  const tokensCopy = t.integration.tokens;
  const mcp = t.integration.mcp;
  const integrationTokensPath = `${workspacePath(workspaceId, 'integration')}?tab=tokens`;
  const workspaceName = getWorkspace(workspaceId)?.name ?? workspaceId;

  if (!canManageTokens && myRole !== undefined) {
    return <Navigate to={integrationTokensPath} replace />;
  }

  async function handleCreate(
    values: { name: string },
    scope: 'read' | 'write',
    grants: { mcp: string[]; http: string[] },
  ) {
    setSubmitting(true);
    try {
      const secret = await integration.createApiToken(values.name, scope, grants);
      navigate(integrationTokensPath, {
        replace: true,
        ...(secret ? { state: { createdTokenSecret: secret } } : {}),
      });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <ConsolePageLayout
      crumbs={[
        { label: t.core.workspace_nav.platform.workspaces, to: '/workspaces' },
        { label: workspaceName, to: workspacePath(workspaceId, 'graph') },
        { label: t.integration.menu.integration, to: `${workspacePath(workspaceId, 'integration')}?tab=tokens` },
        { label: tokensCopy.create_page_title },
      ]}
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" asChild>
            <Link to={integrationTokensPath}>{t.core.common.cancel}</Link>
          </Button>
          <Button
            size="sm"
            type="submit"
            form={FORM_ID}
            disabled={submitting}
            data-testid="api-token-create-submit"
          >
            {submitting ? t.core.common.loading : mcp.create_button}
          </Button>
        </div>
      }
    >
      <div className="flex-none pb-6">
        <ApiTokenCreateForm
          formId={FORM_ID}
          mcpTools={mcpTools}
          httpOperations={httpOperations}
          onSubmit={handleCreate}
        />
      </div>
    </ConsolePageLayout>
  );
}
