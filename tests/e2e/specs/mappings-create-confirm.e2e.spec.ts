import { expect, test } from '@playwright/test';

import { e2eWorkspaceApiPath } from '../api-v1-path.js';
import {
  bearerToken,
  createProposedRelationMappingViaUi,
  defaultWorkspaceId,
  ingestPasteText,
  registerFreshUser,
  waitForLedgerSurfacePhrases,
} from '../helpers.js';

test('create relation mapping in UI and confirm materializes typed facts', async ({ page }) => {
  test.setTimeout(180_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);
  await ingestPasteText(page, workspaceId, 'Alice knows Bob.');

  const phrases = await waitForLedgerSurfacePhrases(page, workspaceId);
  const signature = phrases.find((phrase) => /know/i.test(phrase)) ?? phrases[0];
  const targetUri = 'http://example.org/e2eKnows';

  await createProposedRelationMappingViaUi(page, workspaceId, signature, targetUri);

  const mappingRow = page.locator('tr').filter({ hasText: signature });
  await expect(mappingRow).toBeVisible({ timeout: 30_000 });
  await mappingRow.getByRole('button', { name: /Confirm|确认/i }).click();

  const token = await bearerToken(page);
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
