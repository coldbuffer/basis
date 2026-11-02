import { lazy, Suspense } from 'react';
import { WorkspaceConsoleShell } from '@/components/app/shared/workspace/frame/ws-console-shell.js';
import { Spinner } from '@/components/ui/spinner.js';
import { useI18n } from '@/i18n/context.js';

const SparqlScreen = lazy(() =>
  import('@/modules/workspace/analyze/pages/sparql.js').then((module) => ({
    default: module.SparqlScreen,
  })),
);

const ReasoningScreen = lazy(() =>
  import('@/modules/workspace/analyze/pages/reasoning.js').then((module) => ({
    default: module.ReasoningScreen,
  })),
);

function TabSuspenseFallback({ label }: { label: string }) {
  return (
    <div className="flex flex-1 items-center justify-center gap-2 text-sm text-muted-foreground">
      <Spinner className="size-4" />
      {label}
    </div>
  );
}

export function AnalyzeSparqlPanel({
  workspaceId,
  className,
}: {
  workspaceId: string;
  className?: string;
}) {
  const { t } = useI18n();

  return (
    <WorkspaceConsoleShell
      workspaceId={workspaceId}
      className={className}
      feature="sparql"
      capabilityOk={(caps) => caps.sparql}
    >
      <Suspense fallback={<TabSuspenseFallback label={t.analyze.hub.loading_sparql} />}>
        <SparqlScreen workspaceId={workspaceId} />
      </Suspense>
    </WorkspaceConsoleShell>
  );
}

export function AnalyzeReasoningPanel({
  workspaceId,
  className,
}: {
  workspaceId: string;
  className?: string;
}) {
  const { t } = useI18n();

  return (
    <WorkspaceConsoleShell
      workspaceId={workspaceId}
      className={className}
      feature="sparql"
      capabilityOk={(caps) => caps.reasoning}
    >
      <Suspense fallback={<TabSuspenseFallback label={t.analyze.hub.loading_reasoning} />}>
        <ReasoningScreen workspaceId={workspaceId} />
      </Suspense>
    </WorkspaceConsoleShell>
  );
}
