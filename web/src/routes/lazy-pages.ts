import { lazy } from 'react';

export const AdminConnectorsPage = lazy(() =>
  import('@/modules/admin-connectors/index.js').then((m) => ({
    default: m.AdminConnectorsPage,
  })),
);
export const AuditPage = lazy(() =>
  import('@/modules/admin-audit/index.js').then((m) => ({ default: m.AuditPage })),
);
export const WorkspacesPage = lazy(() =>
  import('@/modules/admin-workspaces/index.js').then((m) => ({ default: m.WorkspacesPage })),
);
export const ModelsPage = lazy(() =>
  import('@/modules/admin-models/index.js').then((m) => ({ default: m.ModelsPage })),
);
export const SettingsPage = lazy(() =>
  import('@/modules/admin-settings/index.js').then((m) => ({ default: m.SettingsPage })),
);
export const UsersPage = lazy(() =>
  import('@/modules/admin-users/index.js').then((m) => ({ default: m.UsersPage })),
);
export const AlertsPage = lazy(() =>
  import('@/modules/alerts/index.js').then((m) => ({ default: m.AlertsPage })),
);
export const AnalyzePage = lazy(() =>
  import('@/modules/analyze/index.js').then((m) => ({ default: m.AnalyzePage })),
);
export const ConnectorsPage = lazy(() =>
  import('@/modules/connectors/index.js').then((m) => ({
    default: m.ConnectorsPage,
  })),
);
export const ConnectorOAuthCallbackPage = lazy(() =>
  import('@/modules/connectors/pages/oauth-callback.js').then((m) => ({
    default: m.ConnectorOAuthCallbackPage,
  })),
);
export const ConnectorMappingNewPage = lazy(() =>
  import('@/modules/connectors/pages/mapping-new.js').then((m) => ({
    default: m.ConnectorMappingNewPage,
  })),
);
export const ConnectorMappingEditPage = lazy(() =>
  import('@/modules/connectors/pages/mapping-edit.js').then((m) => ({
    default: m.ConnectorMappingEditPage,
  })),
);
export const ActivityLogPage = lazy(() =>
  import('@/modules/activity-log/index.js').then((m) => ({
    default: m.ActivityLogPage,
  })),
);
export const DocsPage = lazy(() =>
  import('@/modules/docs/index.js').then((m) => ({ default: m.DocsPage })),
);
export const EntitiesPage = lazy(() =>
  import('@/modules/entities/index.js').then((m) => ({ default: m.EntitiesPage })),
);
export const GraphPage = lazy(() =>
  import('@/modules/graph/index.js').then((m) => ({ default: m.GraphPage })),
);
export const GraphDiffPage = lazy(() =>
  import('@/modules/graph/pages/diff.js').then((m) => ({ default: m.GraphDiffPage })),
);
export const IntegrationPage = lazy(() =>
  import('@/modules/integration/index.js').then((m) => ({
    default: m.IntegrationPage,
  })),
);
export const IntegrationTokenNewPage = lazy(() =>
  import('@/modules/integration/index.js').then((m) => ({
    default: m.IntegrationTokenNewPage,
  })),
);
export const LibraryPage = lazy(() =>
  import('@/modules/library/index.js').then((m) => ({ default: m.LibraryPage })),
);
export const LineagePage = lazy(() =>
  import('@/modules/lineage/index.js').then((m) => ({ default: m.LineagePage })),
);
export const MappingsPage = lazy(() =>
  import('@/modules/mappings/index.js').then((m) => ({ default: m.MappingsPage })),
);
export const OntologyPage = lazy(() =>
  import('@/modules/ontology/index.js').then((m) => ({
    default: m.OntologyPage,
  })),
);
export const ProcessingPage = lazy(() =>
  import('@/modules/processing/index.js').then((m) => ({
    default: m.ProcessingPage,
  })),
);
export const ReviewPage = lazy(() =>
  import('@/modules/review/index.js').then((m) => ({ default: m.ReviewPage })),
);
export const DataQualityPage = lazy(() =>
  import('@/modules/data-quality/index.js').then((m) => ({ default: m.DataQualityPage })),
);
export const SearchPage = lazy(() =>
  import('@/modules/search/index.js').then((m) => ({ default: m.SearchPage })),
);
export const WorkspaceSettingsPage = lazy(() =>
  import('@/modules/settings/index.js').then((m) => ({
    default: m.WorkspaceSettingsPage,
  })),
);
export const SetupPage = lazy(() =>
  import('@/modules/setup/index.js').then((m) => ({ default: m.SetupPage })),
);
export const SwaggerPage = lazy(() =>
  import('@/modules/swagger/index.js').then((m) => ({ default: m.SwaggerPage })),
);
export const VocabularyPage = lazy(() =>
  import('@/modules/vocabulary/index.js').then((m) => ({
    default: m.VocabularyPage,
  })),
);
