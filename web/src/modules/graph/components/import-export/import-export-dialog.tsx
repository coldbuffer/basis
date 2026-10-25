import { lazy, Suspense, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { WorkspaceHostProvider } from '@/lib/workspace/ws-http.js';
import { buildWorkspaceHttpConfig } from '@/lib/workspace/ws-host.js';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog.js';
import { Spinner } from '@/components/ui/spinner.js';
import { useI18n } from '@/i18n/context.js';
import { workspaceReviewPath } from '@/lib/nav/nav-config.js';
const ImportExportScreen = lazy(() =>
  import('./import-export-screen.js').then((module) => ({
    default: module.ImportExportScreen,
  })),
);

const importExportQueryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});

export function ImportExportDialog({
  workspaceId,
  open,
  onOpenChange,
  focus = 'import',
  seedNodeIds,
}: {
  workspaceId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  focus?: 'import' | 'export';
  seedNodeIds?: string[];
}) {
  const { t, locale } = useI18n();
  const ie = t.graph.import_export;
  const navigate = useNavigate();
  const config = useMemo(() => buildWorkspaceHttpConfig(workspaceId, locale), [workspaceId, locale]);
  const isImport = focus === 'import';

  function goToReviewQueue() {
    onOpenChange(false);
    navigate(workspaceReviewPath(workspaceId));
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[min(92vh,48rem)] flex-col gap-0 overflow-hidden p-0 sm:max-w-4xl">
        <DialogHeader className="border-b border-border px-6 py-4 text-left">
          <DialogTitle>
            {isImport ? ie.import_dialog_title : ie.export_dialog_title}
          </DialogTitle>
          <DialogDescription className="space-y-2">
            {isImport ? ie.import_dialog_desc : ie.export_dialog_desc}
            {isImport ? (
              <span className="block">
                <Link
                  className="text-primary underline-offset-4 hover:underline"
                  to={workspaceReviewPath(workspaceId)}
                  onClick={() => onOpenChange(false)}
                >
                  {ie.open_review_queue}
                </Link>
              </span>
            ) : null}
          </DialogDescription>
        </DialogHeader>
        <div className="basis-ws-console relative min-h-0 flex-1 overflow-y-auto bg-background text-foreground">
          <QueryClientProvider client={importExportQueryClient}>
            <WorkspaceHostProvider config={config}>
              <Suspense
                fallback={
                  <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
                    <Spinner className="size-4" />
                    {t.core.common.loading}
                  </div>
                }
              >
                <ImportExportScreen
                  workspaceId={workspaceId}
                  focusSection={focus}
                  seedNodeIds={seedNodeIds}
                  onImportQueued={goToReviewQueue}
                  importQueuedActionLabel={ie.open_review_queue}
                />
              </Suspense>
            </WorkspaceHostProvider>
          </QueryClientProvider>
        </div>
      </DialogContent>
    </Dialog>
  );
}
