import { useParams } from 'react-router-dom';
import { LedgerEvidenceInspector } from './components/ledger-evidence-inspector.js';
import { SourcesPage } from '@/modules/workspace/library/pages/sources.js';
import { WorkspaceRouteShell } from '@/lib/workspace/ws-context.js';

export function LibraryPage() {
  const { id } = useParams();
  if (!id) return null;

  return (
    <WorkspaceRouteShell>
      <div
        className="basis-library-shell flex min-h-0 w-full flex-1 flex-col"
        data-workspace-id={id}
      >
        <LedgerEvidenceInspector workspaceId={id} />
        <SourcesPage />
      </div>
    </WorkspaceRouteShell>
  );
}
