import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Spinner } from '@/components/ui/spinner.js';
import { Button } from '@/components/ui/button.js';
import { useI18n } from '@/i18n/context.js';
import { formatLocaleDateTime } from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import { formatUserFacingApiError } from '@/lib/errors/api-error-message.js';
import {
  documentTimelineDiffRange,
  documentTimelineEventLine,
  type DocumentTimelineResponse,
} from '@/modules/workspace/library/lib/document-timeline.js';
import { graphPath } from '@/modules/workspace/graph/lib/graph-url-state.js';
import { workspaceGraphDiffPath } from '@/lib/nav/nav-config.js';
import { workspaceOpenApiGET } from '@/lib/openapi/client.js';

export function DocumentTimelinePanel({
  workspaceId,
  documentRef,
  docId,
}: {
  workspaceId: string;
  documentRef: string;
  docId: string;
}) {
  const { t, locale } = useI18n();
  const copy = t.library.sources.timeline;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<DocumentTimelineResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    void workspaceOpenApiGET<DocumentTimelineResponse>(
      workspaceId,
      `documents/${encodeURIComponent(documentRef)}/timeline`,
    )
      .then((payload) => {
        if (!cancelled) setData(payload);
      })
      .catch((err) => {
        if (!cancelled) setError(formatUserFacingApiError(err, locale as Locale));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [documentRef, workspaceId, locale]);

  const events = data?.events ?? [];
  const diffRange = documentTimelineDiffRange(events);

  return (
    <section
      className="border-t border-border bg-muted/20 px-4 py-4"
      data-testid="workspace-document-timeline-panel"
      aria-labelledby="workspace-document-timeline-heading"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id="workspace-document-timeline-heading" className="text-sm font-semibold text-foreground">
          {copy.title}
        </h3>
        <span className="font-mono text-xs text-muted-foreground">{docId}</span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">{copy.hint}</p>
      {loading ? (
        <div className="mt-3 flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner className="size-4" />
          {t.core.common.loading}
        </div>
      ) : error ? (
        <p className="mt-3 text-sm text-destructive">{error}</p>
      ) : events.length === 0 ? (
        <p className="mt-3 text-sm text-muted-foreground">{copy.empty}</p>
      ) : (
        <ol className="mt-3 max-h-56 space-y-2 overflow-y-auto text-sm">
          {[...events].reverse().map((event, index) => {
            const at = event.at?.trim();
            const key = `${event.kind}-${at ?? 'na'}-${index}`;
            return (
              <li
                key={key}
                className="rounded-md border border-border/70 bg-background/80 px-3 py-2"
              >
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="text-foreground">{documentTimelineEventLine(copy, event)}</span>
                  <div className="flex shrink-0 flex-wrap items-center gap-2">
                    {at ? (
                      <time className="text-xs tabular-nums text-muted-foreground">
                        {formatLocaleDateTime(locale as Locale, at)}
                      </time>
                    ) : null}
                    {at ? (
                      <Link
                        to={graphPath(workspaceId, { at })}
                        className="text-xs font-medium text-primary underline-offset-4 hover:underline"
                        data-testid="workspace-document-timeline-graph-at"
                      >
                        {copy.view_graph_at}
                      </Link>
                    ) : null}
                  </div>
                </div>
                {event.invalidated_at ? (
                  <p className="mt-1 text-xs text-muted-foreground">
                    {copy.invalidated_at}{' '}
                    {formatLocaleDateTime(locale as Locale, event.invalidated_at)}
                  </p>
                ) : null}
              </li>
            );
          })}
        </ol>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        {diffRange.to ? (
          <Button type="button" variant="outline" size="sm" asChild>
            <Link
              to={graphPath(workspaceId, { at: diffRange.to })}
              data-testid="workspace-document-timeline-graph-latest"
            >
              {copy.open_graph_at_latest}
            </Link>
          </Button>
        ) : null}
        <Button type="button" variant="outline" size="sm" asChild>
          <Link
            to={workspaceGraphDiffPath(workspaceId, diffRange.from, diffRange.to)}
            data-testid="workspace-document-timeline-graph-diff"
          >
            {copy.open_graph_diff}
          </Link>
        </Button>
      </div>
    </section>
  );
}
