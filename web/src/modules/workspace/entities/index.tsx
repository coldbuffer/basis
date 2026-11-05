import { useCallback } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { ConsolePageLayout } from '@/components/app/shared/console/index.js';
import { DerivedFactsPanel } from '@/modules/workspace/entities/components/derived-facts-panel.js';
import { LedgerEntityBrowser } from '@/components/app/shared/workspace/ledger-entity-browser.js';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs.js';
import { useI18n } from '@/i18n/context.js';
import { useWorkspaceCatalog } from '@/lib/workspace/context.js';
import {
  parseEntitiesUrlState,
  type EntitiesTab,
} from '@/modules/workspace/entities/lib/entities-url-state.js';
import { workspacePath } from '@/lib/nav/nav-config.js';

export function EntitiesPage() {
  const { id } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const { statementId: focusStatementId, tab } = parseEntitiesUrlState(searchParams.toString());
  const { t } = useI18n();
  const { getWorkspace } = useWorkspaceCatalog();

  const setTab = useCallback(
    (next: EntitiesTab) => {
      const sp = new URLSearchParams(searchParams);
      if (next === 'derived') {
        sp.set('tab', 'derived');
        sp.delete('statement');
      } else {
        sp.delete('tab');
      }
      setSearchParams(sp, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  if (!id) return null;

  const p = t.entities.page;
  const tabSwitcher = (
    <Tabs value={tab} onValueChange={(v) => setTab(v as EntitiesTab)}>
      <TabsList aria-label={t.entities.menu.entities}>
        <TabsTrigger value="entities" className="px-3 text-xs">
          {p.tab_entities}
        </TabsTrigger>
        <TabsTrigger value="derived" className="px-3 text-xs">
          {p.tab_derived}
        </TabsTrigger>
      </TabsList>
    </Tabs>
  );

  return (
    <ConsolePageLayout
      crumbs={[
        { label: t.core.workspace_nav.platform.workspaces, to: '/workspaces' },
        { label: getWorkspace(id)?.name ?? id, to: workspacePath(id, 'graph') },
        { label: t.entities.menu.entities },
      ]}
      subtitle={p.subtitle}
      className="gap-6 [&>:last-child]:min-h-0 [&>:last-child]:flex-none"
    >
      {tab === 'derived' ? (
        <DerivedFactsPanel workspaceId={id} toolbarPrefix={tabSwitcher} />
      ) : (
        <LedgerEntityBrowser
          workspaceId={id}
          focusStatementId={focusStatementId}
          toolbarPrefix={tabSwitcher}
        />
      )}
    </ConsolePageLayout>
  );
}
