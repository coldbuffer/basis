import { expect, test } from '@playwright/test';

import { defaultWorkspaceId, ingestDocumentViaApi, registerFreshUser } from '../helpers';

test('search graph tab runs query', async ({ page }) => {
  test.setTimeout(120_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);
  await ingestDocumentViaApi(page, workspaceId, 'Graph search smoke node.');

  await page.goto(`/workspaces/${workspaceId}/search?scope=graph&q=smoke`);

  const unavailable = page.getByRole('heading', {
    name: /工作区不可用|Workspace unavailable/i,
  });
  if ((await unavailable.count()) > 0) {
    test.skip(true, 'graph search requires graph_runtime');
  }

  await expect(page.getByPlaceholder(/Search graph nodes|搜索图谱节点/i)).toHaveValue('smoke', {
    timeout: 30_000,
  });
  await expect(page.getByText(/result|结果/i).first()).toBeVisible({ timeout: 60_000 });
});
