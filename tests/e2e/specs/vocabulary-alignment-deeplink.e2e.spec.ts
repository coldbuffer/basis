import { expect, test } from '@playwright/test';

import { bearerToken, defaultWorkspaceId, registerFreshUser, skipUnlessWorkspaceGraphWrite } from '../helpers.js';
import { e2eWorkspaceApiPath } from '../api-v1-path.js';

test('vocabulary alignment deep link opens suggest dialog with source ontology', async ({ page }) => {
  test.setTimeout(90_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);
  await skipUnlessWorkspaceGraphWrite(page, workspaceId);

  const token = await bearerToken(page);
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  const createdA = await page.request.post(e2eWorkspaceApiPath(workspaceId, 'ontology'), {
    headers,
    data: { name: 'E2E Align A', namespace: 'http://example.org/e2e-align-a' },
  });
  expect(createdA.ok()).toBeTruthy();
  const uriA = (await createdA.json()) as { uri: string };

  const createdB = await page.request.post(e2eWorkspaceApiPath(workspaceId, 'ontology'), {
    headers,
    data: { name: 'E2E Align B', namespace: 'http://example.org/e2e-align-b' },
  });
  expect(createdB.ok()).toBeTruthy();

  const params = new URLSearchParams({
    tab: 'alignments',
    alignSuggest: '1',
    alignOntology: uriA.uri,
  });
  await page.goto(`/workspaces/${workspaceId}/ontology?${params.toString()}`);

  await expect(page.getByRole('tab', { name: /Vocabulary alignment|词汇对齐/i })).toHaveAttribute(
    'data-state',
    'active',
    { timeout: 60_000 },
  );

  const dialog = page.getByTestId('vocabulary-alignment-suggest-dialog');
  await expect(dialog).toBeVisible({ timeout: 30_000 });

  const sourceSelect = page.getByTestId('vocabulary-alignment-suggest-source');
  await expect(sourceSelect).toHaveValue(uriA.uri, { timeout: 30_000 });
});
