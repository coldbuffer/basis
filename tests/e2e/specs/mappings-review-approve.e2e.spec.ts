import { expect, test } from '@playwright/test';

import { e2eWorkspaceApiPath } from '../api-v1-path.js';
import {
  bearerToken,
  createProposedRelationMappingViaUi,
  defaultWorkspaceId,
  ingestPasteText,
  registerFreshUser,
  skipIfReviewWorkspaceUnavailable,
  waitForLedgerSurfacePhrases,
  waitForOntologyMappingReviewItemId,
} from '../helpers.js';

test('approve ontology mapping in smart review materializes typed facts', async ({ page }) => {
  test.setTimeout(180_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);
  await ingestPasteText(page, workspaceId, 'Alice knows Bob.');

  const phrases = await waitForLedgerSurfacePhrases(page, workspaceId);
  const signature = phrases.find((phrase) => /know/i.test(phrase)) ?? phrases[0];
  const targetUri = 'http://example.org/e2eKnowsReview';

  await createProposedRelationMappingViaUi(page, workspaceId, signature, targetUri);
  const reviewItemId = await waitForOntologyMappingReviewItemId(page, workspaceId, signature);

  await page.goto(`/workspaces/${workspaceId}/review?reviewItem=${encodeURIComponent(reviewItemId)}`);
  await skipIfReviewWorkspaceUnavailable(page);

  const card = page.locator(`#review-item-${reviewItemId}`);
  await expect(card).toBeVisible({ timeout: 60_000 });
  await card.getByRole('button', { name: /Approve mapping|批准映射/i }).click();
  await expect(page.getByTestId('review-approve-decision-link')).toBeVisible({ timeout: 30_000 });

  const token = await bearerToken(page);
  await expect
    .poll(
      async () => {
        const mappingsRes = await page.request.get(e2eWorkspaceApiPath(workspaceId, 'mappings'), {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!mappingsRes.ok()) {
          return '';
        }
        const mappings = (await mappingsRes.json()) as {
          mappings?: Array<{ signature: string; status: string }>;
        };
        const row = (mappings.mappings ?? []).find((m) => m.signature === signature);
        return row?.status ?? '';
      },
      { timeout: 60_000 },
    )
    .toBe('confirmed');

  await expect
    .poll(
      async () => {
        const response = await page.request.get(
          e2eWorkspaceApiPath(workspaceId, 'ledger/typed-facts'),
          { headers: { Authorization: `Bearer ${token}` } },
        );
        if (!response.ok()) {
          return 0;
        }
        const body = (await response.json()) as { facts?: unknown[] };
        return body.facts?.length ?? 0;
      },
      { timeout: 60_000 },
    )
    .toBeGreaterThan(0);
});
