import { expect, test } from '@playwright/test';

import { defaultWorkspaceId, registerFreshUser, skipUnlessWorkspaceGraphWrite } from '../helpers';

test('graph toolbar links to graph diff workspace', async ({ page }) => {
  test.setTimeout(120_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);
  await skipUnlessWorkspaceGraphWrite(page, workspaceId);

  await page.goto(`/workspaces/${workspaceId}/graph`);

  const unavailable = page.getByRole('heading', {
    name: /工作区不可用|Workspace unavailable/i,
  });
  if ((await unavailable.count()) > 0) {
    test.skip(true, 'graph workspace requires graph_runtime');
  }

  const diffLink = page.getByTestId('workspace-graph-open-diff');
  await expect(diffLink).toBeVisible({ timeout: 60_000 });
  await diffLink.click();
  await expect(page).toHaveURL(/graph-diff/);
  await expect(page.locator('.basis-graph-diff-page')).toBeVisible({ timeout: 60_000 });
  await expect(page.getByRole('button', { name: /^Compare$|^对比$/ })).toBeVisible({
    timeout: 30_000,
  });
});
