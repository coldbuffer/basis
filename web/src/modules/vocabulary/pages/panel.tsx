import { lazy, Suspense, useMemo } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { WorkspaceHostProvider } from '@/lib/workspace/ws-http.js';
import { buildWorkspaceHttpConfig } from '@/lib/workspace/ws-host.js';
import { useWorkspaceCapabilities } from '@/lib/workspace/capabilities.js';
import { WorkspaceUnavailable } from '@/components/app/shared/workspace/frame/ws-unavailable.js';
import { Spinner } from '@/components/ui/spinner.js';
import { useI18n } from '@/i18n/context.js';
import { cn } from '@/lib/utils.js';
import { govEmbeddedPanelShell } from '@/lib/ui-classes/governance-ui.js';
import { OntologyWorkspaceCatalogProvider } from '@/components/app/shared/workspace/ontology-workspace-context.js';

const VocabularyScreen = lazy(() =>
  import('@/modules/vocabulary/pages/screen.js').then((module) => ({
    default: module.VocabularyScreen,
  })),
);

const hubQueryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});

export function VocabularyPanel({
  workspaceId,
  className,
}: {
  workspaceId: string;
  className?: string;
}) {
  const { t, locale } = useI18n();
  const { caps, loading: capsLoading } = useWorkspaceCapabilities();
  const config = useMemo(() => buildWorkspaceHttpConfig(workspaceId, locale), [workspaceId, locale]);

  if (!capsLoading && caps && !caps.vocabulary) {
    return <WorkspaceUnavailable workspaceId={workspaceId} feature="vocabulary" />;
  }

  return (
    <div
      className={cn(
        'basis-ws-console basis-vocabulary-hub relative flex w-full flex-col overflow-hidden bg-background text-foreground',
        govEmbeddedPanelShell,
        className,
      )}
      data-workspace-id={workspaceId}
    >
      <QueryClientProvider client={hubQueryClient}>
        <WorkspaceHostProvider config={config}>
          <OntologyWorkspaceCatalogProvider workspaceId={workspaceId}>
            <Suspense
              fallback={
                <div className="flex flex-1 items-center justify-center gap-2 text-sm text-muted-foreground">
                  <Spinner className="size-4" />
                  {t.vocabulary.page.loading_view}
                </div>
              }
            >
              <VocabularyScreen workspaceId={workspaceId} />
            </Suspense>
          </OntologyWorkspaceCatalogProvider>
        </WorkspaceHostProvider>
      </QueryClientProvider>
    </div>
  );
}
