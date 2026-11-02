import { Button } from '@/components/ui/button.js';
import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';
import { useI18n } from '@/i18n/context.js';
import { exWsHint, exWsScrollFill, exWsSplitMain } from '@/lib/ui-classes/ws-ui.js';
import type { ConceptNode } from '../lib/types.js';

interface PropertyPanelProps {
  concept: ConceptNode | null;
  onSelectConcept: (concept: ConceptNode) => void;
}

function SectionLabel({ icon, title }: { icon: string; title: string }) {
  return (
    <h3 className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
      <PublicIcon name={icon} size={13} />
      {title}
    </h3>
  );
}

export function PropertyPanel({ concept, onSelectConcept }: PropertyPanelProps) {
  const { t } = useI18n();
  const copy = t.vocabulary.page;
  const narrower = concept?.children ?? [];
  const altLabels = concept?.alt_labels ?? [];

  return (
    <div className={exWsSplitMain}>
      <div className="flex h-12 shrink-0 items-center gap-2 border-b border-border px-4">
        <PublicIcon name="tag" size={13} className="shrink-0 text-muted-foreground" />
        {concept ? (
          <span className="min-w-0 truncate text-sm font-medium text-foreground">{concept.pref_label}</span>
        ) : (
          <span className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">{copy.concept}</span>
        )}
        {concept?.notation ? (
          <span className="shrink-0 font-mono text-[11px] text-muted-foreground">{concept.notation}</span>
        ) : null}
      </div>

      <div className={exWsScrollFill}>
        {!concept ? (
          <div className="flex h-full flex-col items-center justify-center px-6 text-center">
            <PublicIcon name="tag" size={18} className="mb-2 text-muted-foreground" />
            <p className="text-sm font-medium text-foreground">{copy.empty_title}</p>
            <p className={`${exWsHint} mt-1 max-w-xs`}>{copy.empty_body}</p>
          </div>
        ) : (
          <div className="flex flex-col gap-6 px-4 py-4">
            <p className="truncate font-mono text-[11px] text-muted-foreground" title={concept.uri}>
              {concept.uri}
            </p>

            {altLabels.length > 0 ? (
              <section>
                <SectionLabel icon="tag" title={copy.alt_labels} />
                <div className="flex flex-wrap gap-1.5">
                  {altLabels.map((label) => (
                    <span key={label} className="rounded-md bg-muted px-2 py-1 text-[12px] text-foreground">
                      {label}
                    </span>
                  ))}
                </div>
              </section>
            ) : null}

            {concept.description ? (
              <section>
                <SectionLabel icon="file-01" title={copy.description} />
                <p className="text-sm leading-relaxed text-foreground">{concept.description}</p>
              </section>
            ) : null}

            <section>
              <SectionLabel icon="git-branch-01" title={copy.narrower} />
              {narrower.length > 0 ? (
                <div className="flex flex-col">
                  {narrower.map((child) => (
                    <Button
                      key={child.uri}
                      type="button"
                      variant="ghost"
                      className="h-8 w-full justify-start gap-2 rounded-md px-2 text-left text-[13px] font-normal text-foreground"
                      onClick={() => onSelectConcept(child)}
                    >
                      <PublicIcon name={child.children?.length ? 'folder' : 'file-01'} size={13} className="shrink-0 text-muted-foreground" />
                      <span className="min-w-0 truncate">{child.pref_label}</span>
                    </Button>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">{copy.leaf}</p>
              )}
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
