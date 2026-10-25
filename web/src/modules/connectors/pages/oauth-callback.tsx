import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { ConsolePageLayout } from '@/components/app/shared/console/index.js';
import { Spinner } from '@/components/ui/spinner.js';
import { useI18n } from '@/i18n/context.js';
import type { Locale } from '@/i18n/locale.js';
import { formatUserFacingApiError } from '@/lib/errors/api-error-message.js';
import {
  clearPendingConnectorOAuth,
  workspaceConnectorOAuthRedirectUri,
  resolveOAuthCallbackPending,
  runOAuthCodeExchangeOnce,
} from '@/modules/connectors/lib/connector-oauth.js';
import { writeEndUserSubjectId } from '@/modules/connectors/lib/end-user-subject.js';
import { workspaceConnectorsAuthorizationHref } from '@/modules/connectors/lib/playground-deep-link.js';
import { workspaceOpenApiPOST } from '@/lib/openapi/client.js';

type CallbackPhase = 'working' | 'success' | 'error';

export function ConnectorOAuthCallbackPage() {
  const { id: workspaceId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { t, locale } = useI18n();
  const c = t.connectors.page.catalog;
  const [phase, setPhase] = useState<CallbackPhase>('working');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!workspaceId) {
      setPhase('error');
      setErrorMessage(c.oauth_callback_missing);
      return;
    }

    const code = searchParams.get('code');
    const state = searchParams.get('state');
    const oauthError = searchParams.get('error');

    if (oauthError) {
      clearPendingConnectorOAuth();
      setPhase('error');
      setErrorMessage(searchParams.get('error_description') ?? oauthError);
      return;
    }

    if (!code || !state) {
      setPhase('error');
      setErrorMessage(c.oauth_callback_missing);
      return;
    }

    const pending = resolveOAuthCallbackPending(workspaceId, state);
    if (!pending) {
      setPhase('error');
      setErrorMessage(c.oauth_callback_state_mismatch);
      return;
    }

    void runOAuthCodeExchangeOnce(workspaceId, code, async () => {
      try {
        const redirectUri =
          pending.redirectUri || workspaceConnectorOAuthRedirectUri(workspaceId);
        if (pending.endUserSubjectId) {
          await workspaceOpenApiPOST(
            workspaceId,
            `connectors/embed/oauth/${pending.service}/exchange`,
            {
              body: {
                code,
                state,
                redirect_uri: redirectUri,
                code_verifier: pending.codeVerifier ?? null,
                                connection_scope: 'end_user',
                subject_id: pending.endUserSubjectId,
                connection_config: pending.connectionConfig,
              },
            },
          );
        } else {
          await workspaceOpenApiPOST(workspaceId, `connectors/oauth/${pending.service}/exchange`, {
            body: {
              code,
              redirect_uri: redirectUri,
              code_verifier: pending.codeVerifier ?? null,
                            connection_config: pending.connectionConfig,
            },
          });
        }
        clearPendingConnectorOAuth(state);
        setPhase('success');
        toast.success(c.oauth_callback_success);
        if (pending.endUserSubjectId?.trim()) {
          writeEndUserSubjectId(workspaceId, pending.endUserSubjectId);
        }
        // Do not pass service/subject_id — authorization tab deep-link opens the connect dialog.
        navigate(workspaceConnectorsAuthorizationHref(workspaceId), { replace: true });
      } catch (err) {
        clearPendingConnectorOAuth();
        setPhase('error');
        setErrorMessage(formatUserFacingApiError(err, locale as Locale));
      }
    });
  }, [c, workspaceId, locale, navigate, searchParams]);

  if (!workspaceId) {
    return null;
  }

  const crumbs = [
    { label: t.core.workspace_nav.platform.workspaces, to: '/workspaces' },
    {
      label: t.core.workspace_nav.workspace_zones.knowledge,
      to: workspaceConnectorsAuthorizationHref(workspaceId),
    },
    { label: c.oauth_callback_title },
  ];

  return (
    <ConsolePageLayout crumbs={crumbs}>
      <div
        className="flex min-h-[12rem] flex-col items-center justify-center gap-3 text-center"
        data-testid="connector-oauth-callback"
      >
        {phase === 'working' ? (
          <>
            <Spinner className="size-6" />
            <p className="text-sm text-muted-foreground">{c.oauth_callback_working}</p>
          </>
        ) : null}
        {phase === 'error' ? (
          <>
            <p className="text-sm text-destructive">{errorMessage ?? c.oauth_callback_failed}</p>
            <Link
              className="text-sm text-primary hover:underline"
              to={workspaceConnectorsAuthorizationHref(workspaceId)}
            >
              {c.oauth_back_to_authorization}
            </Link>
          </>
        ) : null}
        {phase === 'success' ? (
          <p className="text-sm text-muted-foreground">{c.oauth_callback_success}</p>
        ) : null}
      </div>
    </ConsolePageLayout>
  );
}
