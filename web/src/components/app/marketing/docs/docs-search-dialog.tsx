import { Search } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { Button } from '@/components/ui/button.js';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog.js';
import { Input } from '@/components/ui/input.js';
import { useI18n } from '@/i18n/context.js';
import {
  productDocsSearchEntries,
  searchProductDocs,
} from '@/modules/docs/lib/product-docs-search-index.js';
import { cn } from '@/lib/utils.js';

type DocsSearchDialogProps = {
  /** Distinguishes sidebar vs mobile triggers (both mount in the DOM). */
  triggerTestId?: string;
};

export function DocsSearchDialog({ triggerTestId = 'docs-search-open' }: DocsSearchDialogProps) {
  const { t, locale } = useI18n();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');

  const entries = useMemo(() => productDocsSearchEntries(locale), [locale]);
  const results = useMemo(() => searchProductDocs(entries, query), [entries, query]);

  const openSearch = useCallback(() => setOpen(true), []);
  const closeSearch = useCallback(() => {
    setOpen(false);
    setQuery('');
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        const target = event.target as HTMLElement | null;
        const tag = target?.tagName?.toLowerCase();
        if (tag === 'input' || tag === 'textarea' || target?.isContentEditable) return;
        event.preventDefault();
        setOpen((value) => !value);
      }
      if (event.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  const go = (url: string) => {
    navigate(url);
    closeSearch();
  };

  return (
    <>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="h-8 w-full justify-start gap-2 text-muted-foreground font-normal"
        onClick={openSearch}
        data-testid={triggerTestId}
      >
        <Search className="size-3.5 shrink-0" aria-hidden />
        <span className="truncate">{t.docs.page.search_placeholder}</span>
        <kbd
          className="ml-auto hidden rounded border border-border bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground sm:inline"
        >
          ⌘K
        </kbd>
      </Button>

      <Dialog open={open} onOpenChange={(next) => (next ? openSearch() : closeSearch())}>
        <DialogContent className="gap-0 p-0 sm:max-w-lg" showCloseButton>
          <DialogHeader className="border-b border-border px-4 py-3">
            <DialogTitle className="text-base">{t.docs.page.search_title}</DialogTitle>
            <DialogDescription className="sr-only">{t.docs.page.search_placeholder}</DialogDescription>
          </DialogHeader>
          <div className="px-4 py-3">
            <Input
              autoFocus
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t.docs.page.search_placeholder}
              aria-label={t.docs.page.search_placeholder}
              data-testid="docs-search-input"
            />
          </div>
          <ul className="max-h-72 overflow-y-auto border-t border-border px-2 py-2" role="listbox">
            {query.trim() && results.length === 0 ? (
              <li className="px-2 py-6 text-center text-sm text-muted-foreground">{t.docs.page.search_empty}</li>
            ) : null}
            {results.map((entry) => (
              <li key={entry.url}>
                <button
                  type="button"
                  role="option"
                  className={cn(
                    'w-full rounded-md px-2 py-2 text-left transition-colors hover:bg-accent',
                  )}
                  onClick={() => go(entry.url)}
                >
                  <span className="block text-sm font-medium text-foreground">{entry.title}</span>
                  {entry.description ? (
                    <span className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{entry.description}</span>
                  ) : null}
                </button>
              </li>
            ))}
          </ul>
        </DialogContent>
      </Dialog>
    </>
  );
}
