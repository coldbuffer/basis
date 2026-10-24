import { useSearchParams } from 'react-router-dom';
import { ConsolePageLayout } from '@/components/app/shared/console/index.js';
import { ModelCatalogTab } from '@/components/admin/models/model-catalog-tab.js';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs.js';
import { useI18n } from '@/i18n/context.js';
import { usePlatformAdminCrumbs } from '@/lib/admin/use-platform-admin-crumbs.js';

type ModelTab = 'llm' | 'embed';

export function ModelsPage() {
  const { t } = useI18n();
  const m = t.admin_models.page;
  const [searchParams, setSearchParams] = useSearchParams();
  const tab: ModelTab = searchParams.get('tab') === 'embed' ? 'embed' : 'llm';
  const tabSubtitle = tab === 'embed' ? m.embed_subtitle : m.llm_subtitle;
  const crumbs = usePlatformAdminCrumbs(t.admin_models.page.nav_title);

  return (
    <ConsolePageLayout
      crumbs={crumbs}
      subtitle={tabSubtitle}
    >
      <Tabs
        value={tab}
        onValueChange={(value) => {
          setSearchParams({ tab: value }, { replace: true });
        }}
      >
        <TabsList>
          <TabsTrigger value="llm">{m.tab_llm}</TabsTrigger>
          <TabsTrigger value="embed">{m.tab_embed}</TabsTrigger>
        </TabsList>

        <TabsContent value="llm" className="mt-4">
          <ModelCatalogTab kind="llm" />
        </TabsContent>

        <TabsContent value="embed" className="mt-4">
          <ModelCatalogTab kind="embed" />
        </TabsContent>
      </Tabs>
    </ConsolePageLayout>
  );
}
