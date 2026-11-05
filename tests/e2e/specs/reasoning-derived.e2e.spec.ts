import { expect, test } from '@playwright/test';

import { defaultWorkspaceId, registerFreshUser, runReasoningApplyViaApi } from '../helpers';

test('reasoning apply_to_graph shows derived facts on entities page', async ({ page }) => {
  test.setTimeout(120_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);
  const stamp = `E2eDeriv${Date.now()}`;
  const entityA = `${stamp}A`;
  const entityB = `${stamp}B`;

  try {
    const out = await runReasoningApplyViaApi(
      page,
      workspaceId,
      [`parent(${entityA}, ${entityB})`],
      [`IF parent(${entityA}, ${entityB}) THEN ancestor(${entityA}, ${entityB})`],
    );
    expect((out.derived_facts_persisted?.created ?? 0) >= 1).toBeTruthy();
  } catch (err) {
    if (String(err).includes('graph_runtime_unavailable')) {
      test.skip(true, 'reasoning/run requires graph_runtime');
    }
    throw err;
  }

  await page.goto(`/workspaces/${workspaceId}/entities?tab=derived`);
  await expect(
    page.getByRole('heading', { name: /Recent reasoning|最近推理/i }),
  ).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/urn:basis:pred:ancestor|ancestor/).first()).toBeVisible();

  await page.getByRole('tab', { name: /^Entities$|^实体名录$/ }).click();
  await page.getByPlaceholder(/Entity label|实体名称/i).fill(entityA);
  await page.getByRole('button', { name: /^Search$|^搜索$/ }).click();
  await expect(page.getByText(entityA).first()).toBeVisible({ timeout: 60_000 });
  const row = page.getByRole('row').filter({ hasText: entityA });
  await row.getByRole('button').click();
  await page.getByRole('menuitem', { name: /View facts|查看事实/i }).click();
  await expect(page.getByRole('heading', { name: /^Derived$|^派生$/i })).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByText(/urn:basis:pred:ancestor|ancestor/).first()).toBeVisible();
});
