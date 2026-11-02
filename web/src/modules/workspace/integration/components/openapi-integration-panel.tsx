import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import SwaggerUI from 'swagger-ui-react';
import 'swagger-ui-react/swagger-ui.css';
import { Button } from '@/components/ui/button.js';
import { useI18n } from '@/i18n/context.js';
import { basisApiBaseUrl } from '@/lib/openapi/basis-api-url.js';
import { getToken } from '@/lib/session/auth-token.js';
import { workspaceApiRoot } from '@/lib/workspace/api-path.js';
import { openapiSpecUrl } from '@/lib/openapi/spec-url.js';

type OpenApiIntegrationPanelProps = {
  workspaceId: string;
};

export function OpenApiIntegrationPanel({ workspaceId }: OpenApiIntegrationPanelProps) {
  const { t } = useI18n();
  const copy = t.integration.openapi;
  const specUrl = useMemo(() => openapiSpecUrl('workspaces'), []);
  const apiBase = useMemo(() => {
    const origin = basisApiBaseUrl().replace(/\/$/, '');
    return `${origin}${workspaceApiRoot(workspaceId)}`;
  }, [workspaceId]);

  const requestInterceptor = useMemo(
    () => (req: { headers?: Record<string, string> }) => {
      const token = getToken();
      if (token) {
        req.headers = { ...req.headers, Authorization: `Bearer ${token}` };
      }
      return req;
    },
    [],
  );

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-border">
      <div className="flex shrink-0 flex-col gap-2 border-b border-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-muted-foreground">{copy.hint}</p>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" asChild>
            <a href={specUrl} target="_blank" rel="noreferrer">
              {copy.download_json}
            </a>
          </Button>
          <Button variant="outline" size="sm" asChild>
            <Link to="/swagger">{copy.open_swagger}</Link>
          </Button>
        </div>
      </div>
      <div className="shrink-0 space-y-1 border-b border-border px-4 py-2 text-xs text-muted-foreground">
        <p>
          {copy.api_base_label}{' '}
          <code className="rounded bg-muted px-1 py-0.5 font-mono text-[11px] text-foreground">
            {apiBase}
          </code>
        </p>
        <p>{copy.workspace_id_try_it_out}</p>
        <p data-testid="workspace-integration-export-ui-hint">
          {copy.export_ui_hint}{' '}
          <Link to={`/workspaces/${workspaceId}/settings?tab=graph`} className="text-primary hover:underline">
            {copy.export_ui_link}
          </Link>
        </p>
        <p data-testid="workspace-integration-alerts-api-hint">{copy.alerts_api_hint}</p>
      </div>
      <div className="basis-swagger-panel min-h-0 flex-1 overflow-auto">
        <SwaggerUI
          key={specUrl}
          url={specUrl}
          docExpansion="list"
          defaultModelsExpandDepth={-1}
          tryItOutEnabled
          requestInterceptor={requestInterceptor}
        />
      </div>
    </div>
  );
}
