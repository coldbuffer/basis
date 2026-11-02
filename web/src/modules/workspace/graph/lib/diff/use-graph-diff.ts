import { useEffect, useState } from 'react';
import type { Locale } from '@/i18n/locale.js';
import { formatUserFacingApiError } from '@/lib/errors/api-error-message.js';
import type { GraphDiffOverlayInput } from '@/modules/workspace/graph/lib/diff/graph-diff-overlay.js';
import { workspaceOpenApiGET } from '@/lib/openapi/client.js';

export type GraphStagingManifest = {
  session_key?: string;
  from_time?: string;
  to_time?: string;
};

export type GraphDiffPayload = GraphDiffOverlayInput & {
  from_time: string;
  to_time: string;
  summary: {
    nodes_added: number;
    nodes_removed: number;
    nodes_modified: number;
    edges_added: number;
    edges_removed: number;
  };
};

export function useWorkspaceGraphDiff(
  workspaceId: string,
  diffFrom: string | undefined,
  diffTo: string | undefined,
  locale: Locale,
): {
  diff: GraphDiffPayload | null;
  stagingSessionKey: string | null;
  loading: boolean;
  error: string | null;
} {
  const [diff, setDiff] = useState<GraphDiffPayload | null>(null);
  const [stagingSessionKey, setStagingSessionKey] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const from = diffFrom?.trim();
    const to = diffTo?.trim();
    if (!workspaceId || !from || !to) {
      setDiff(null);
      setStagingSessionKey(null);
      setError(null);
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    void workspaceOpenApiGET<{ diff: GraphDiffPayload; manifest?: GraphStagingManifest }>(
      workspaceId,
      'graph/staging',
      {
        params: { query: { from, to } },
      },
    )
      .then((data) => {
        if (cancelled) return;
        setDiff(data.diff);
        const key = data.manifest?.session_key?.trim();
        setStagingSessionKey(key || null);
      })
      .catch((err) => {
        if (!cancelled) setError(formatUserFacingApiError(err, locale));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [diffFrom, diffTo, workspaceId, locale]);

  return { diff, stagingSessionKey, loading, error };
}
