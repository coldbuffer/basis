import { useEffect, useMemo, useRef, useState } from 'react';
import { Input } from '@/components/ui/input.js';
import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';
import { useI18n } from '@/i18n/context.js';
import { workspaceOpenApiGET } from '@/lib/openapi/client.js';
import { vocabularyAlignmentPickerHits } from '@/modules/mappings/lib/vocabulary-alignment-picker.js';
import { cn } from '@/lib/utils.js';

type OntologySearchHit = {
  uri: string;
  label: string;
  entity_type: string;
};

type OntologyAlignmentRow = {
  source_uri: string;
  target_uri: string;
  source_label?: string | null;
  target_label?: string | null;
  relation: string;
};

type PickerRow = {
  uri: string;
  label: string;
  fromVocabularyAlignment: boolean;
};

type OntologyUriPickerProps = {
  workspaceId: string;
  entityType: 'class' | 'property';
  value: string;
  onValueChange: (uri: string) => void;
  disabled?: boolean;
  placeholder: string;
  hint: string;
  emptySearchLabel: string;
  className?: string;
};

/** Search ontology hub entities inline (dialog-safe, no portal). */
export function OntologyUriPicker({
  workspaceId,
  entityType,
  value,
  onValueChange,
  disabled,
  placeholder,
  hint,
  emptySearchLabel,
  className,
}: OntologyUriPickerProps) {
  const { t } = useI18n();
  const alignmentBadge = t.mappings.page.ontology_uri_picker_vocabulary_alignment;
  const rootRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState(value);
  const [hits, setHits] = useState<OntologySearchHit[]>([]);
  const [alignments, setAlignments] = useState<OntologyAlignmentRow[]>([]);
  const [searching, setSearching] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!open) setQuery(value);
  }, [open, value]);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      const root = rootRef.current;
      if (!root || root.contains(event.target as Node)) return;
      setOpen(false);
    };
    document.addEventListener('pointerdown', onPointerDown);
    return () => document.removeEventListener('pointerdown', onPointerDown);
  }, [open]);

  useEffect(() => {
    if (!open || alignments.length > 0) return;
    void (async () => {
      try {
        const rows = await workspaceOpenApiGET<OntologyAlignmentRow[]>(workspaceId, 'ontology/alignments');
        setAlignments(Array.isArray(rows) ? rows : []);
      } catch {
        setAlignments([]);
      }
    })();
  }, [alignments.length, open, workspaceId]);

  useEffect(() => {
    if (!open) return;
    const q = query.trim();
    if (!q) {
      setHits([]);
      setSearching(false);
      return;
    }
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      void (async () => {
        setSearching(true);
        try {
          const rows = await workspaceOpenApiGET<OntologySearchHit[]>(workspaceId, 'ontology/search', {
            params: {
              query: { q, limit: 40, entity_type: entityType },
            },
          });
          setHits(Array.isArray(rows) ? rows : []);
        } catch {
          setHits([]);
        } finally {
          setSearching(false);
        }
      })();
    }, 320);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [entityType, open, query, workspaceId]);

  const rows = useMemo((): PickerRow[] => {
    const q = query.trim();
    if (!q) return [];
    const alignmentHits = vocabularyAlignmentPickerHits(alignments, entityType, q);
    const seen = new Set(alignmentHits.map((hit) => hit.uri));
    const merged: PickerRow[] = alignmentHits.map((hit) => ({
      uri: hit.uri,
      label: hit.label,
      fromVocabularyAlignment: true,
    }));
    for (const hit of hits) {
      if (seen.has(hit.uri)) continue;
      seen.add(hit.uri);
      merged.push({ uri: hit.uri, label: hit.label || hit.uri, fromVocabularyAlignment: false });
    }
    return merged;
  }, [alignments, entityType, hits, query]);

  const displayValue = open ? query : value;

  return (
    <div ref={rootRef} className={cn('relative w-full space-y-1', className)}>
      <p className="text-[11px] text-muted-foreground">{hint}</p>
      <div className="relative">
        <Input
          value={displayValue}
          placeholder={placeholder}
          disabled={disabled}
          autoComplete="off"
          className="pr-8 font-mono text-xs"
          onFocus={() => {
            setQuery(value);
            setOpen(true);
          }}
          onChange={(event) => {
            const next = event.target.value;
            setQuery(next);
            onValueChange(next);
            setOpen(true);
          }}
          onKeyDown={(event) => {
            if (event.key === 'Escape') {
              setOpen(false);
              setQuery(value);
            }
          }}
        />
        {searching ? (
          <PublicIcon
            name="loader-01"
            size={14}
            className="pointer-events-none absolute top-1/2 right-2.5 -translate-y-1/2 animate-spin text-muted-foreground"
          />
        ) : null}
      </div>
      {open && query.trim() ? (
        <div
          className="absolute right-0 left-0 z-[200] mt-1 max-h-56 overflow-y-auto overscroll-y-contain rounded-md border border-border bg-popover p-1 text-popover-foreground shadow-md"
          role="listbox"
        >
          {searching && rows.length === 0 ? (
            <p className="flex items-center gap-2 px-2 py-2 text-sm text-muted-foreground">
              <PublicIcon name="loader-01" size={14} className="animate-spin" />
            </p>
          ) : null}
          {!searching && rows.length === 0 ? (
            <p className="px-2 py-2 text-center text-sm text-muted-foreground">{emptySearchLabel}</p>
          ) : (
            rows.map((hit) => (
              <button
                key={hit.uri}
                type="button"
                role="option"
                aria-selected={hit.uri === value}
                className={cn(
                  'flex w-full flex-col rounded-sm px-2 py-1.5 text-left outline-none hover:bg-accent hover:text-accent-foreground',
                  hit.uri === value && 'bg-accent/60',
                )}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => {
                  onValueChange(hit.uri);
                  setQuery(hit.uri);
                  setOpen(false);
                }}
              >
                <span className="flex items-center gap-2 truncate text-sm text-foreground">
                  <span className="truncate">{hit.label || hit.uri}</span>
                  {hit.fromVocabularyAlignment ? (
                    <span className="shrink-0 rounded border border-border px-1 py-0 text-[9px] font-medium text-muted-foreground">
                      {alignmentBadge}
                    </span>
                  ) : null}
                </span>
                <span className="truncate font-mono text-[10px] text-muted-foreground">{hit.uri}</span>
              </button>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}
