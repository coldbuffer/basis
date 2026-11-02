import { useState } from 'react';
import { exWsPageRow } from '@/lib/ui-classes/ws-ui.js';
import { Sidebar } from '../components/sidebar.js';
import { PropertyPanel } from '../components/property.js';
import type { ConceptNode } from '../lib/types.js';
import { VocabularyWorkspaceCatalogProvider } from '../components/vocabulary-workspace-context.js';

export function VocabularyScreen({ workspaceId }: { workspaceId: string }) {
  const [selectedConcept, setSelectedConcept] = useState<ConceptNode | null>(null);

  return (
    <VocabularyWorkspaceCatalogProvider workspaceId={workspaceId}>
      <div className={exWsPageRow}>
        <Sidebar onSelectConcept={setSelectedConcept} />
        <PropertyPanel concept={selectedConcept} onSelectConcept={setSelectedConcept} />
      </div>
    </VocabularyWorkspaceCatalogProvider>
  );
}
