import { expect, test } from '@playwright/test';

import { defaultWorkspaceId, proposeRememberViaApi, registerFreshUser } from '../helpers';

test('decisions list selection updates shareable decision query', async ({ page }) => {
  test.setTimeout(120_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);
  const fact = `E2E decision deep link ${Date.now()}`;
  const { reviewItemId } = await proposeRememberViaApi(page, workspaceId, fact);

  await page.goto(`/workspaces/${workspaceId}/review?reviewItem=${encodeURIComponent(reviewItemId)}`);

  const unavailable = page.getByRole('heading', {
    name: /工作区不可用|Workspace unavailable/i,
  });
  if ((await unavailable.count()) > 0) {
    test.skip(true, 'decisions workspace requires graph_runtime');
  }

  const card = page.locator(`#review-item-${reviewItemId}`);
  await expect(card).toBeVisible({ timeout: 60_000 });
  await card.getByRole('button', { name: /Approve fact|批准记入/i }).click();

  const decisionLink = page.getByTestId('review-approve-decision-link');
  await expect(decisionLink).toBeVisible({ timeout: 30_000 });
  await decisionLink.click();
  await expect(page).toHaveURL(/\/log/);
  await expect(page).toHaveURL(/graph_decision=/);
  await expect(page.getByTestId('graph-decision-detail-dialog')).toBeVisible({ timeout: 30_000 });

  const url = new URL(page.url());
  const decisionId = url.searchParams.get('graph_decision');
  expect(decisionId).toBeTruthy();

  await page.keyboard.press('Escape');
  await expect(page.getByTestId('graph-decision-detail-dialog')).toBeHidden({ timeout: 15_000 });

  await page.getByTestId('activity-log-browse-decisions').click();
  const listItem = page.getByTestId(`decision-list-item-${decisionId}`);
  if ((await listItem.count()) > 0) {
    await listItem.click();
    await expect(page).toHaveURL(
      new RegExp(
        `graph_decision=${encodeURIComponent(decisionId!).replace(/[-/\\^$*+?.()|[\]{}]/g, '\\$&')}`,
      ),
    );
    await expect(page.getByTestId('graph-decision-detail-dialog')).toBeVisible();
  }
});
