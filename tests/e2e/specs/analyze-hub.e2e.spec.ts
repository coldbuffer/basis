import { expect, test } from '@playwright/test';

import { defaultWorkspaceId, registerFreshUser } from '../helpers';

test('analyze hub tabs (SPARQL and reasoning)', async ({ page }) => {
  test.setTimeout(90_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);

  await page.goto(`/workspaces/${workspaceId}/analyze`);
  await expect(page.getByRole('tab', { name: /^SPARQL$/i })).toHaveAttribute('data-state', 'active');
  await expect(page.getByText(/SPARQL and reasoning HTTP|SPARQL 与规则推理 HTTP/i)).toBeVisible({
    timeout: 60_000,
  });

  await page.getByRole('tab', { name: /Reasoning|规则推理/i }).click();
  await expect(page).toHaveURL(new RegExp(`/workspaces/${workspaceId}/analyze\\?tab=reasoning`), {
    timeout: 30_000,
  });

  const unavailable = page.getByRole('heading', {
    name: /工作区不可用|Workspace unavailable/i,
  });
  if ((await unavailable.count()) > 0) {
    test.skip(true, 'reasoning workspace requires graph_runtime');
  }

  await expect(page.getByRole('button', { name: /Run reasoning|运行推理/i })).toBeVisible({
    timeout: 60_000,
  });
  await page.getByRole('button', { name: /Run reasoning|运行推理/i }).click();
  await expect(page.getByText(/^Results$|^结果$/i).first()).toBeVisible({ timeout: 60_000 });
});
