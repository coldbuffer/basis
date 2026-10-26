import { expect, test } from '@playwright/test';

import {
  bearerToken,
  defaultWorkspaceId,
  registerFreshUser,
  skipUnlessWorkspaceGraphWrite,
} from '../helpers.js';
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
  await skipUnlessWorkspaceGraphWrite(page, workspaceId);
  const token = await bearerToken(page);
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
  for (const [name, namespace] of [
    ['E2E Align A', 'http://example.org/e2e-align-a'],
    ['E2E Align B', 'http://example.org/e2e-align-b'],
  ] as const) {
    const created = await page.request.post(e2eWorkspaceApiPath(workspaceId, 'ontology'), {
      headers,
      data: { name, namespace },
    });
    expect(created.ok(), await created.text()).toBeTruthy();
  }

  await page.goto(`/workspaces/${workspaceId}/ontology?tab=alignments`);
  const alignTab = page.getByRole('tab', { name: /Vocabulary alignment|词汇对齐/i });
  await expect(alignTab).toBeVisible({ timeout: 60_000 });
  await expect(alignTab).toHaveAttribute('data-state', 'active', { timeout: 60_000 });
});
