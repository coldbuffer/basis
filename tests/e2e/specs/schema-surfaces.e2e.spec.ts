import { expect, test } from '@playwright/test';

import { bearerToken, defaultWorkspaceId, registerFreshUser } from '../helpers.js';
import { e2eWorkspaceApiPath } from '../api-v1-path.js';

test('statement mappings page shows extraction-focused chrome', async ({ page }) => {
  test.setTimeout(90_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);

  await page.goto(`/workspaces/${workspaceId}/mappings`);
  await expect(page).toHaveURL(/\/ontology\?tab=statement/, { timeout: 30_000 });
  await expect(page.getByRole('tab', { name: /Semantic alignment|语义对齐/i })).toHaveAttribute(
    'data-state',
    'active',
  );
  await expect(page.getByText(/Connections → Table sync|连接.*表同步/i).first()).toBeVisible();
  await expect(page.getByRole('button', { name: /New mapping|新建映射/i })).toBeVisible();
});

test('vocabulary hub loads', async ({ page }) => {
  test.setTimeout(90_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);

  await page.goto(`/workspaces/${workspaceId}/vocabulary`);
  await expect(page.getByText(/Vocabulary|受控词表|词表/i).first()).toBeVisible({
    timeout: 30_000,
  });
});

test('ontology hub alignments tab', async ({ page }) => {
  test.setTimeout(90_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);
  const token = await bearerToken(page);
  await page.request.post(e2eWorkspaceApiPath(workspaceId, 'ontology'), {
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    data: { name: 'E2E B', namespace: 'http://example.org/e2e-b' },
  });

  await page.goto(`/workspaces/${workspaceId}/ontology?tab=alignments`);
  await expect(page.getByRole('tab', { name: /Vocabulary alignment|词汇对齐/i })).toHaveAttribute(
    'data-state',
    'active',
  );
});
