import { Link } from 'react-router-dom';
import { ConfirmAlertDialog } from '@/components/app/shared/console/ConfirmAlertDialog.js';
import {
  DataPanel,
  DataPanelBody,
  DataPanelHeader,
} from '@/components/app/shared/console/index.js';
import { Badge } from '@/components/ui/badge.js';
import { Button } from '@/components/ui/button.js';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog.js';
import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';
import { useI18n } from '@/i18n/context.js';
import { fmt, formatLocaleDateTime } from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import { mcpTokenScopeLabel } from '@/modules/workspace/integration/lib/mcp-labels.js';

export type ApiTokenRow = {
  id: string;
  name: string;
  scope: string;
  workspace_ids: string[];
  mcp_allowed_operations?: string[];
  http_allowed_operations?: string[];
  created_at: string;
  expires_at: string | null;
  last_used_at: string | null;
  revoked_at: string | null;
  secret?: string;
};

type ApiTokensPanelProps = {
  apiTokens: ApiTokenRow[];
  canManageTokens: boolean;
  createTokenPath: string;
  createdSecret: string | null;
  onDismissCreatedSecret: () => void;
  onCopy: (text: string) => void | Promise<void>;
  onDeleteToken: (tokenId: string) => void | Promise<void>;
};

export function ApiTokensPanel({
  apiTokens,
  canManageTokens,
  createTokenPath,
  createdSecret,
  onDismissCreatedSecret,
  onCopy,
  onDeleteToken,
}: ApiTokensPanelProps) {
  const { t, locale } = useI18n();
  const mcp = t.integration.mcp;
  const tokensCopy = t.integration.tokens;
  const activeTokens = apiTokens.filter((row) => !row.revoked_at);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <Dialog
        open={Boolean(createdSecret)}
        onOpenChange={(open) => {
          if (!open) onDismissCreatedSecret();
        }}
      >
        <DialogContent className="sm:max-w-lg" data-testid="api-token-secret-dialog">
          <DialogHeader>
            <DialogTitle>{mcp.secret_dialog_title}</DialogTitle>
            <DialogDescription>{mcp.secret_once}</DialogDescription>
          </DialogHeader>
          <code className="block break-all rounded-md border border-border bg-muted/40 px-3 py-2.5 font-mono text-xs text-foreground">
            {createdSecret}
          </code>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="outline" onClick={onDismissCreatedSecret}>
              {mcp.secret_dismiss}
            </Button>
            <Button
              type="button"
              disabled={!createdSecret}
              onClick={() => createdSecret && void onCopy(createdSecret)}
            >
              {mcp.copy_token}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <DataPanel className="min-h-0 flex-1" data-testid="integration-tokens-panel">
        <DataPanelHeader
          title={tokensCopy.list_title}
          subtitle={tokensCopy.list_subtitle}
          actions={
            canManageTokens ? (
              <Button size="sm" asChild data-testid="api-token-create-link">
                <Link to={createTokenPath}>
                  <PublicIcon name="plus-01" size={14} className="mr-1" />
                  {mcp.create_button}
                </Link>
              </Button>
            ) : null
          }
        />
        <DataPanelBody padded={false} className="min-h-0 overflow-auto">
          {!canManageTokens ? (
            <p className="px-4 py-6 text-sm text-muted-foreground">{mcp.admin_only}</p>
          ) : activeTokens.length === 0 ? (
            <p className="px-4 py-6 text-sm text-muted-foreground">{tokensCopy.list_empty}</p>
          ) : (
            <div className="divide-y divide-border">
              {activeTokens.map((row) => {
                const restricted =
                  Boolean(row.mcp_allowed_operations?.length) ||
                  Boolean(row.http_allowed_operations?.length);
                return (
                  <div
                    key={row.id}
                    className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm"
                    data-testid={`api-token-row-${row.id}`}
                  >
                    <div className="min-w-0 flex-1 space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="outline" className="text-[10px]">
                          {mcpTokenScopeLabel(mcp, row.scope)}
                        </Badge>
                        <span className="font-medium text-foreground">{row.name}</span>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {mcp.last_used}:{' '}
                        {row.last_used_at
                          ? formatLocaleDateTime(locale as Locale, row.last_used_at)
                          : mcp.last_used_never}
                      </p>
                      <div className="flex flex-wrap items-center gap-2 pt-0.5">
                        {restricted ? (
                          <>
                            <Badge variant="secondary" className="font-mono text-[10px]">
                              {fmt(tokensCopy.restricted_grants_badge, {
                                mcp: row.mcp_allowed_operations?.length ?? 0,
                                http: row.http_allowed_operations?.length ?? 0,
                              })}
                            </Badge>
                          </>
                        ) : (
                          <Badge variant="outline" className="text-[10px]">
                            {tokensCopy.unrestricted_badge}
                          </Badge>
                        )}
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center justify-end gap-2">
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={!row.secret}
                        title={row.secret ? undefined : mcp.copy_token_unavailable}
                        onClick={() => row.secret && void onCopy(row.secret)}
                      >
                        {mcp.copy_token}
                      </Button>
                      {canManageTokens ? (
                        <ConfirmAlertDialog
                          title={mcp.delete_title}
                          description={mcp.delete_confirm}
                          destructive
                          onConfirm={() => onDeleteToken(row.id)}
                          trigger={
                            <Button type="button" size="sm" variant="ghost" className="text-destructive">
                              {mcp.delete}
                            </Button>
                          }
                        />
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </DataPanelBody>
      </DataPanel>
    </div>
  );
}
