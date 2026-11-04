import { lazy } from 'react';

export const AuditPage = lazy(() =>
  import('@/modules/admin/audit/index.js').then((m) => ({ default: m.AuditPage })),
);
export const WorkspacesPage = lazy(() =>
  import('@/modules/admin/workspaces/index.js').then((m) => ({ default: m.WorkspacesPage })),
);
export const ModelsPage = lazy(() =>
  import('@/modules/admin/models/index.js').then((m) => ({ default: m.ModelsPage })),
);
export const SettingsPage = lazy(() =>
  import('@/modules/admin/settings/index.js').then((m) => ({ default: m.SettingsPage })),
);
export const UsersPage = lazy(() =>
  import('@/modules/admin/users/index.js').then((m) => ({ default: m.UsersPage })),
);
export const AlertsPage = lazy(() =>
  import('@/modules/workspace/alerts/index.js').then((m) => ({ default: m.AlertsPage })),
);
export const AnalyzePage = lazy(() =>
  import('@/modules/workspace/analyze/index.js').then((m) => ({ default: m.AnalyzePage })),
);
export const ActivityLogPage = lazy(() =>
  import('@/modules/workspace/activity-log/index.js').then((m) => ({
    default: m.ActivityLogPage,
  })),
);
export const DocsPage = lazy(() =>
  import('@/modules/public/docs/index.js').then((m) => ({ default: m.DocsPage })),
);
export const EntitiesPage = lazy(() =>
  import('@/modules/workspace/entities/index.js').then((m) => ({ default: m.EntitiesPage })),
);
export const GraphPage = lazy(() =>
  import('@/modules/workspace/graph/index.js').then((m) => ({ default: m.GraphPage })),
);
export const GraphDiffPage = lazy(() =>
  import('@/modules/workspace/graph/pages/diff.js').then((m) => ({ default: m.GraphDiffPage })),
);
export const IntegrationPage = lazy(() =>
  import('@/modules/workspace/integration/index.js').then((m) => ({
    default: m.IntegrationPage,
  })),
);
export const IntegrationTokenNewPage = lazy(() =>
  import('@/modules/workspace/integration/index.js').then((m) => ({
    default: m.IntegrationTokenNewPage,
  })),
);
export const LibraryPage = lazy(() =>
  import('@/modules/workspace/library/index.js').then((m) => ({ default: m.LibraryPage })),
);
export const LineagePage = lazy(() =>
  import('@/modules/workspace/lineage/index.js').then((m) => ({ default: m.LineagePage })),
);
export const MappingsPage = lazy(() =>
  import('@/modules/workspace/mappings/index.js').then((m) => ({ default: m.MappingsPage })),
);
export const OntologyPage = lazy(() =>
  import('@/modules/workspace/ontology/index.js').then((m) => ({
    default: m.OntologyPage,
  })),
);
export const ProcessingPage = lazy(() =>
  import('@/modules/workspace/processing/index.js').then((m) => ({
    default: m.ProcessingPage,
  })),
);
export const SqlCatalogPage = lazy(() =>
  import('@/modules/workspace/sql-catalog/index.js').then((m) => ({
    default: m.SqlCatalogPage,
  })),
);
export const ReviewPage = lazy(() =>
  import('@/modules/workspace/review/index.js').then((m) => ({ default: m.ReviewPage })),
);
export const DataQualityPage = lazy(() =>
  import('@/modules/workspace/data-quality/index.js').then((m) => ({ default: m.DataQualityPage })),
);
export const SearchPage = lazy(() =>
  import('@/modules/workspace/search/index.js').then((m) => ({ default: m.SearchPage })),
);
export const WorkspaceSettingsPage = lazy(() =>
  import('@/modules/workspace/settings/index.js').then((m) => ({
    default: m.WorkspaceSettingsPage,
  })),
);
export const SetupPage = lazy(() =>
  import('@/modules/public/setup/index.js').then((m) => ({ default: m.SetupPage })),
);
export const SwaggerPage = lazy(() =>
  import('@/modules/public/swagger/index.js').then((m) => ({ default: m.SwaggerPage })),
);
export const VocabularyPage = lazy(() =>
  import('@/modules/workspace/vocabulary/index.js').then((m) => ({
    default: m.VocabularyPage,
  })),
);
