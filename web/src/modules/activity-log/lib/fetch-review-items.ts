import { workspaceOpenApiGET } from '@/lib/openapi/client.js';
import type { ReviewItemSummaryInput } from '@/modules/review/lib/review-item-summary.js';

type ReviewItemResponse = ReviewItemSummaryInput;

const MAX_SINGLE_FETCHES = 40;

export async function fetchReviewItemsById(
  workspaceId: string,
  itemIds: string[],
): Promise<Map<string, ReviewItemSummaryInput>> {
  const map = new Map<string, ReviewItemSummaryInput>();
  if (itemIds.length === 0) return map;

  try {
    const list = await workspaceOpenApiGET<{ items?: ReviewItemResponse[] }>(
      workspaceId,
      'review/items',
    );
    for (const item of list.items ?? []) {
      if (item?.id) map.set(item.id, item);
    }
  } catch {
    /* queue list optional */
  }

  const missing = itemIds.filter((id) => !map.has(id)).slice(0, MAX_SINGLE_FETCHES);
  await Promise.all(
    missing.map(async (id) => {
      try {
        const body = await workspaceOpenApiGET<{ item?: ReviewItemResponse }>(
          workspaceId,
          `review/items/${encodeURIComponent(id)}`,
        );
        if (body.item?.id) map.set(body.item.id, body.item);
      } catch {
        /* resolved / deleted items */
      }
    }),
  );

  return map;
}
