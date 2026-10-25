import { Navigate, Route, Routes } from 'react-router-dom';
import { PlatformAdminLayout } from '@/components/admin/platform-admin-layout.js';
import { BasisLayout } from '@/components/app/shared/shell/basis-layout.js';
import { HomePage } from '@/modules/home/index.js';
import { LoginPage } from '@/modules/login/index.js';
import {
  AdminConnectorsPage,
  AuditPage,
  DocsPage,
  AlertsPage,
  AnalyzePage,
  ConnectorMappingEditPage,
  ConnectorMappingNewPage,
  ConnectorOAuthCallbackPage,
  ConnectorsPage,
  ActivityLogPage,
  EntitiesPage,
  GraphDiffPage,
  GraphPage,
  IntegrationPage,
  IntegrationTokenNewPage,
  LibraryPage,
  LineagePage,
  MappingsPage,
  OntologyPage,
  ProcessingPage,
  ReviewPage,
  DataQualityPage,
  SearchPage,
  SetupPage,
  WorkspacesPage,
  VocabularyPage,
  ModelsPage,
  SettingsPage,
  WorkspaceSettingsPage,
  SwaggerPage,
  UsersPage,
} from '@/routes/lazy-pages.js';
import { basisAuthRequired } from '@/lib/runtime/basis-runtime.js';
import { useBasisSession } from '@/lib/session/basis-session.js';
import { AdminLandingRedirect } from '@/routes/admin-landing-redirect.js';
import { AdminOnly, WorkspaceDefaultRedirect, SettingsAccess } from '@/routes/guards.js';
import { WorkspacesLandingRedirect } from '@/routes/workspaces-landing-redirect.js';
import { Lazy, WorkspaceLazy } from '@/routes/ui.js';

/** React Router tree for the Basis console (`app.tsx` wraps this in `BasisSessionProvider`). */
export function AppRoutes() {
  const { ready, user, homePath, logout } = useBasisSession();
  const authRequired = basisAuthRequired();

  return (
    <Routes>
      <Route
        path="/"
        element={
          authRequired
            ? ready && user
              ? <Navigate to={homePath} replace />
              : <HomePage />
            : ready
              ? <Navigate to={homePath} replace />
              : null
        }
      />
      <Route
        path="/login"
        element={
          !basisAuthRequired() ? (
            <Navigate to={homePath} replace />
          ) : ready && user ? (
            <Navigate to={homePath} replace />
          ) : (
            <LoginPage />
          )
        }
      />
      <Route path="/swagger" element={<Lazy><SwaggerPage /></Lazy>} />
      <Route path="/docs" element={<Lazy><DocsPage /></Lazy>} />
      <Route path="/docs/*" element={<Lazy><DocsPage /></Lazy>} />
      <Route
        element={
          authRequired && ready && !user ? (
            <Navigate to="/" replace />
          ) : !authRequired && !ready ? null : (
            <BasisLayout onLogout={() => void logout()} />
          )
        }
      >
        <Route path="/workspaces" element={<WorkspacesLandingRedirect />} />
        <Route path="/admin" element={<PlatformAdminLayout />}>
          <Route index element={<AdminLandingRedirect />} />
          <Route
            path="workspaces"
            element={
              <AdminOnly>
                <Lazy><WorkspacesPage /></Lazy>
              </AdminOnly>
            }
          />
          <Route
            path="users"
            element={
              <AdminOnly>
                <Lazy><UsersPage /></Lazy>
              </AdminOnly>
            }
          />
          <Route
            path="models"
            element={
              <AdminOnly>
                <Lazy><ModelsPage /></Lazy>
              </AdminOnly>
            }
          />
          <Route
            path="audit"
            element={
              <AdminOnly>
                <Lazy><AuditPage /></Lazy>
              </AdminOnly>
            }
          />
          <Route
            path="connectors"
            element={
              <AdminOnly>
                <Lazy><AdminConnectorsPage /></Lazy>
              </AdminOnly>
            }
          />
          <Route
            path="settings"
            element={
              <SettingsAccess>
                <Lazy><SettingsPage /></Lazy>
              </SettingsAccess>
            }
          />
        </Route>

        <Route path="/workspaces/setup/*" element={<Lazy><SetupPage /></Lazy>} />
        <Route path="/workspaces/:id" element={<WorkspaceDefaultRedirect />} />
        <Route path="/workspaces/:id/graph-diff" element={<WorkspaceLazy><GraphDiffPage /></WorkspaceLazy>} />
        <Route path="/workspaces/:id/graph" element={<WorkspaceLazy><GraphPage /></WorkspaceLazy>} />
        <Route path="/workspaces/:id/search" element={<WorkspaceLazy><SearchPage /></WorkspaceLazy>} />
        <Route path="/workspaces/:id/sources" element={<Lazy><LibraryPage /></Lazy>} />
        <Route
          path="/workspaces/:id/connectors/mappings/new"
          element={<Lazy><ConnectorMappingNewPage /></Lazy>}
        />
        <Route
          path="/workspaces/:id/connectors/mappings/:mappingId/edit"
          element={<Lazy><ConnectorMappingEditPage /></Lazy>}
        />
        <Route
          path="/workspaces/:id/connectors/oauth/callback"
          element={<Lazy><ConnectorOAuthCallbackPage /></Lazy>}
        />
        <Route path="/workspaces/:id/connectors/:panel" element={<Lazy><ConnectorsPage /></Lazy>} />
        <Route path="/workspaces/:id/connectors" element={<Lazy><ConnectorsPage /></Lazy>} />
        <Route path="/workspaces/:id/processing" element={<Lazy><ProcessingPage /></Lazy>} />
        <Route path="/workspaces/:id/entities" element={<WorkspaceLazy><EntitiesPage /></WorkspaceLazy>} />
        <Route path="/workspaces/:id/log" element={<WorkspaceLazy><ActivityLogPage /></WorkspaceLazy>} />
        <Route path="/workspaces/:id/review" element={<WorkspaceLazy><ReviewPage /></WorkspaceLazy>} />
        <Route path="/workspaces/:id/quality" element={<WorkspaceLazy><DataQualityPage /></WorkspaceLazy>} />
        <Route path="/workspaces/:id/ontology" element={<WorkspaceLazy><OntologyPage /></WorkspaceLazy>} />
        <Route path="/workspaces/:id/analyze" element={<WorkspaceLazy><AnalyzePage /></WorkspaceLazy>} />
        <Route path="/workspaces/:id/vocabulary" element={<WorkspaceLazy><VocabularyPage /></WorkspaceLazy>} />
        <Route path="/workspaces/:id/lineage" element={<WorkspaceLazy><LineagePage /></WorkspaceLazy>} />
        <Route path="/workspaces/:id/mappings" element={<Lazy><MappingsPage /></Lazy>} />
        <Route path="/workspaces/:id/alerts" element={<Lazy><AlertsPage /></Lazy>} />
        <Route path="/workspaces/:id/integration/tokens/new" element={<Lazy><IntegrationTokenNewPage /></Lazy>} />
        <Route path="/workspaces/:id/integration" element={<Lazy><IntegrationPage /></Lazy>} />
        <Route path="/workspaces/:id/settings" element={<Lazy><WorkspaceSettingsPage /></Lazy>} />
      </Route>
    </Routes>
  );
}
