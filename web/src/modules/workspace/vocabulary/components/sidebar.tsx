/**
 * Left sidebar for the Vocabulary workspace.
 */
import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';
import { useState } from 'react';
import { Button } from '@/components/ui/button.js';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog.js';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select.js';
import { useI18n } from '@/i18n/context.js';
import { formatLocaleNumber } from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import { exWsSplitSidebar } from '@/lib/ui-classes/ws-ui.js';
import { useVocabularies, useConceptHierarchy } from '../lib/queries.js';
import { ConceptTree } from './concept-tree';
import { ImportDropzone } from './import-dropzone';
import type { ConceptNode, VocabularyScheme } from '../lib/types.js';

interface SidebarProps {
  onSelectConcept: (concept: ConceptNode) => void;
}

function countConcepts(nodes: ConceptNode[]): number {
  return nodes.reduce((total, node) => total + 1 + countConcepts(node.children ?? []), 0);
}

export function Sidebar({ onSelectConcept }: SidebarProps) {
  const { t, locale } = useI18n();
  const copy = t.vocabulary.page;
  const { data: schemes = [], isLoading: schemesLoading } = useVocabularies();
  const [activeScheme, setActiveScheme] = useState<string | undefined>();
  const [importOpen, setImportOpen] = useState(false);

  const selectedSchemeUri = activeScheme ?? schemes[0]?.uri;

  const {
    data: hierarchy = [],
    isLoading: treeLoading,
  } = useConceptHierarchy(selectedSchemeUri);
  const conceptCount = countConcepts(hierarchy);

  return (
    <div className={exWsSplitSidebar}>
      <div className="flex h-12 shrink-0 items-center gap-2 border-b border-border px-3">
        <span className="flex shrink-0 items-center gap-1.5 text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
          <PublicIcon name="book-01" size={13} />
          {copy.schemes}
        </span>
        {schemesLoading ? (
          <span className="min-w-0 flex-1 truncate text-[11px] text-muted-foreground">{copy.loading_schemes}</span>
        ) : schemes.length === 0 ? (
          <span className="min-w-0 flex-1 truncate text-[11px] text-muted-foreground">{copy.no_schemes}</span>
        ) : (
          <Select
            value={selectedSchemeUri || ''}
            onValueChange={(value) => setActiveScheme(value)}
          >
            <SelectTrigger size="sm" className="min-w-0 flex-1">
              <SelectValue placeholder={copy.pick_scheme} />
            </SelectTrigger>
            <SelectContent>
              {schemes.map((scheme: VocabularyScheme) => (
                <SelectItem key={scheme.uri} value={scheme.uri}>
                  {scheme.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
        {conceptCount > 0 ? (
          <span className="shrink-0 font-mono text-[11px] tabular-nums text-muted-foreground">
            {formatLocaleNumber(locale as Locale, conceptCount)}
          </span>
        ) : null}
        <Button type="button" size="sm" variant="outline" className="h-8 shrink-0 px-2 text-xs" onClick={() => setImportOpen(true)}>
          <PublicIcon name="upload-01" size={14} />
          {copy.import}
        </Button>
      </div>

      <div className="min-h-0 flex-1">
        {treeLoading ? (
          <p className="px-4 py-6 text-sm text-muted-foreground">{copy.loading_tree}</p>
        ) : hierarchy.length === 0 ? (
          <p className="px-4 py-6 text-sm text-muted-foreground">
            {schemes.length === 0 ? copy.no_schemes_hint : copy.no_concepts}
          </p>
        ) : (
          <ConceptTree data={hierarchy} onSelectConcept={onSelectConcept} />
        )}
      </div>

      <Dialog open={importOpen} onOpenChange={setImportOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{copy.import_title}</DialogTitle>
            <DialogDescription>{copy.import_body}</DialogDescription>
          </DialogHeader>
          <ImportDropzone />
        </DialogContent>
      </Dialog>
    </div>
  );
}
