import { expect, test } from '@playwright/test';

import { e2eWorkspaceApiPath } from '../api-v1-path.js';
import {
  approveAndPublishOntologyProposalViaApi,
  bearerToken,
  defaultWorkspaceId,
  registerFreshUser,
  seedOntologyProposalViaApi,
  skipUnlessWorkspaceGraphWrite,
} from '../helpers.js';

test('health panel opens vocabulary alignment suggest from alignment issue', async ({ page }) => {
  test.setTimeout(120_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);
  await skipUnlessWorkspaceGraphWrite(page, workspaceId);

  let seeded: { proposalId: string; ontologyUri: string };
  try {
    seeded = await seedOntologyProposalViaApi(page, workspaceId);
  } catch (err) {
    if (err instanceof Error && err.message === 'e2e_ontology_proposal_unavailable') {
      test.skip(true, 'ontology proposal e2e helper requires data-e2e server');
    }
    throw err;
  }

  await approveAndPublishOntologyProposalViaApi(page, workspaceId, seeded.proposalId);

  const token = await bearerToken(page);
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
  const second = await page.request.post(e2eWorkspaceApiPath(workspaceId, 'ontology'), {
    headers,
    data: { name: 'E2E Health B', namespace: 'http://example.org/e2e-health-b' },
  });
  expect(second.ok()).toBeTruthy();

  await page.goto(`/workspaces/${workspaceId}/ontology?tab=health`);

  const panel = page.getByTestId('ontology-health-panel');
  await expect(panel).toBeVisible({ timeout: 60_000 });

  const ontologySelect = page.getByTestId('ontology-health-ontology-select');
  await ontologySelect.selectOption(seeded.ontologyUri);

  const openAlignment = page.getByTestId('ontology-health-open-vocabulary-alignment');
  await expect(openAlignment).toBeVisible({ timeout: 60_000 });
  await openAlignment.click();

  await expect(page.getByRole('tab', { name: /Vocabulary alignment|词汇对齐/i })).toHaveAttribute(
    'data-state',
    'active',
    { timeout: 30_000 },
  );

  const dialog = page.getByTestId('vocabulary-alignment-suggest-dialog');
  await expect(dialog).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId('vocabulary-alignment-suggest-source')).toHaveValue(seeded.ontologyUri);
});
