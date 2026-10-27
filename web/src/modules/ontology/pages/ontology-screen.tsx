import { HealthPanel } from '../components/health-panel.js';
import { OntologyManager } from '../components/ontology-manager.js';
import { OntologyEditor } from '../components/ontology-editor.js';
import { writeEntitySelection } from '../lib/ontology-url-state.js';
import { OntologyWorkspaceCatalogProvider } from '@/components/app/shared/workspace/ontology-workspace-context.js';
import { cn } from "@/lib/utils.js";
import { wsPage } from "@/lib/ui-classes/console-ws.js";

export type OntologyInteriorPanel = "registry" | "editor" | "health";

interface OntologyScreenProps {
  workspaceId: string;
  panel: OntologyInteriorPanel;
  onJumpToGraphNode?: (nodeId: string) => void;
  pageActionsHosted?: boolean;
  onPageActionsChange?: (actions: { openLoadOntology: () => void } | null) => void;
  onFixInEditor?: (entityUri: string) => void;
  onOpenVocabularyAlignment?: (ontologyUri?: string) => void;
}

export function OntologyScreen({
  workspaceId,
  panel,
  pageActionsHosted = false,
  onPageActionsChange,
  onFixInEditor,
  onOpenVocabularyAlignment,
}: OntologyScreenProps) {
  const handleFixInEditor =
    onFixInEditor ??
    ((entityUri: string) => {
      writeEntitySelection(entityUri);
    });

  const renderPanel = () => {
    switch (panel) {
      case "registry":
        return (
          <OntologyManager
            pageActionsHosted={pageActionsHosted}
            onHubPageActionsChange={onPageActionsChange}
          />
        );
      case "editor":
        return <OntologyEditor />;
      case "health":
        return (
          <HealthPanel
            onFixInEditor={handleFixInEditor}
            onOpenVocabularyAlignment={onOpenVocabularyAlignment}
          />
        );
    }
  };

  return (
    <OntologyWorkspaceCatalogProvider workspaceId={workspaceId}>
      <div className={cn(wsPage, "min-h-0 flex-1")}>
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">{renderPanel()}</div>
      </div>
    </OntologyWorkspaceCatalogProvider>
  );
}
