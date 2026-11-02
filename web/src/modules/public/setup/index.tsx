import { useState } from 'react';
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { WorkspaceCreateDialog } from '@/components/app/shared/workspace/frame/create-dialog.js';
import { EmptyState } from '@/components/app/shared/console/index.js';
import { Button } from '@/components/ui/button.js';
import { useI18n } from '@/i18n/context.js';
import { pickDefaultWorkspaceId, writeActiveWorkspaceId } from '@/lib/workspace/active-id.js';
import { useWorkspaceCatalog } from '@/lib/workspace/context.js';
import { workspacePath } from '@/lib/nav/nav-config.js';

function SetupEmptyView() {
  const { t } = useI18n();
  const p = t.admin_workspaces.page;
  const navigate = useNavigate();
  const { refresh } = useWorkspaceCatalog();
  const [createOpen, setCreateOpen] = useState(false);

  async function onCreated(workspace: { id: string }) {
    writeActiveWorkspaceId(workspace.id);
    await refresh();
    navigate(workspacePath(workspace.id, 'graph'));
  }

  return (
    <>
      <div className="flex min-h-0 flex-1 flex-col p-6">
        <EmptyState
          title={p.empty_title}
          description={p.empty_description}
          action={
            <Button type="button" size="sm" onClick={() => setCreateOpen(true)}>
              {p.create_workspace}
            </Button>
          }
        />
      </div>
      <WorkspaceCreateDialog open={createOpen} onOpenChange={setCreateOpen} onCreated={onCreated} />
    </>
  );
}

/** Routes under `/workspaces/setup/*` when the catalog is empty (sidebar placeholder workspace id). */
export function SetupPage() {
  const { workspaces } = useWorkspaceCatalog();
  const location = useLocation();

  const defaultId = pickDefaultWorkspaceId(workspaces);
  if (defaultId) {
    const suffix = location.pathname.replace(/^\/workspaces\/setup\/?/, '') || 'graph';
    return <Navigate to={workspacePath(defaultId, suffix)} replace />;
  }

  return (
    <Routes>
      <Route path="*" element={<SetupEmptyView />} />
    </Routes>
  );
}