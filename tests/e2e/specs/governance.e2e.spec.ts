import { expect, test } from '@playwright/test';

import {
  defaultWorkspaceId,
  proposeRememberViaApi,
  registerFreshUser,
  seedGovernanceTrippedViaApi,
  seedProcessingFailedViaApi,
  seedStatementConflictViaApi,
  seedSyncFailedViaApi,
} from '../helpers';

test('workspace account menu alerts opens alerts page', async ({ page }) => {
  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);
  await page.goto(`/workspaces/${workspaceId}/sources`);
  await page.getByTestId('basis-account-menu-trigger').click();
  await page.getByRole('menuitem', { name: /^(Alerts|消息提醒)$/ }).click();
  await expect(page).toHaveURL(new RegExp(`/workspaces/${workspaceId}/alerts`), { timeout: 30_000 });
});

test('review queue governance scan button', async ({ page }) => {
  test.setTimeout(120_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);
  await page.goto(`/workspaces/${workspaceId}/review`);

  const unavailable = page.getByRole('heading', {
    name: /工作区不可用|Workspace unavailable/i,
  });
  if ((await unavailable.count()) > 0) {
    test.skip(true, 'review workspace requires graph_runtime');
  }

  const scanBtn = page.getByTestId('review-run-governor');
  await expect(scanBtn).toBeVisible({ timeout: 60_000 });
  await scanBtn.click();
  await expect(page.getByRole('dialog')).toBeVisible({ timeout: 15_000 });
  await page.getByRole('button', { name: /^(Start check|开始检查)$/ }).click();
  await expect(scanBtn).toBeEnabled({ timeout: 120_000 });
});

test('review queue surfaces link to ontology versions tab', async ({ page }) => {
  test.setTimeout(120_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);
  await page.goto(`/workspaces/${workspaceId}/review`);

  const unavailable = page.getByRole('heading', {
    name: /工作区不可用|Workspace unavailable/i,
  });
  if ((await unavailable.count()) > 0) {
    test.skip(true, 'review workspace requires graph_runtime');
  }

  const ontologyLink = page.getByRole('link', {
    name: /Ontology versions|本体版本/i,
  });
  await expect(ontologyLink.first()).toBeVisible({ timeout: 60_000 });
  await ontologyLink.first().click();
  await expect(page).toHaveURL(/\/ontology/);
  await expect(page).toHaveURL(/tab=versions/);
});

test('review queue deep link highlights remembered fact item', async ({ page }) => {
  test.setTimeout(120_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);
  const fact = `E2E remembered fact ${Date.now()}`;
  const { reviewItemId } = await proposeRememberViaApi(page, workspaceId, fact);

  await page.goto(
    `/workspaces/${workspaceId}/review?reviewItem=${encodeURIComponent(reviewItemId)}`,
  );

  const unavailable = page.getByRole('heading', {
    name: /工作区不可用|Workspace unavailable/i,
  });
  if ((await unavailable.count()) > 0) {
    test.skip(true, 'review workspace requires graph_runtime');
  }

  const card = page.locator(`#review-item-${reviewItemId}`);
  await expect(card).toBeVisible({ timeout: 60_000 });
  await expect(card).toHaveClass(/ring-primary/);
  await expect(card.getByText(fact)).toBeVisible();
});

test('sync failed alert opens sources connector focus', async ({ page }) => {
  test.setTimeout(120_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);

  let sourceId: string;
  try {
    ({ sourceId } = await seedSyncFailedViaApi(page, workspaceId));
  } catch (err) {
    if (String(err).includes('e2e_sync_failed_unavailable')) {
      test.skip(true, 'sync-failed e2e helper only on data-e2e API');
    }
    throw err;
  }

  await page.goto(`/workspaces/${workspaceId}/alerts`);
  await page.getByRole('link', { name: /Open sources|打开资料/i }).click();
  await expect(page).toHaveURL(new RegExp(`/workspaces/${workspaceId}/sources$`));
});

test('processing failed alert links to processing job', async ({ page }) => {
  test.setTimeout(120_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);

  let jobId: string;
  try {
    ({ jobId } = await seedProcessingFailedViaApi(page, workspaceId));
  } catch (err) {
    if (String(err).includes('e2e_processing_failed_unavailable')) {
      test.skip(true, 'processing-failed e2e helper only on data-e2e API');
    }
    throw err;
  }

  await page.goto(`/workspaces/${workspaceId}/alerts`);
  await page.getByRole('link', { name: /Open processing job|打开处理任务/i }).click();
  await expect(page).toHaveURL(new RegExp(`/workspaces/${workspaceId}/processing\\?job=${encodeURIComponent(jobId)}`));
  await expect(page.getByTestId(`processing-job-detail-${jobId}`)).toBeVisible({
    timeout: 60_000,
  });
});

test('e2e SHACL conflict seed opens review queue item', async ({ page }) => {
  test.setTimeout(120_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);

  let reviewItemId: string;
  try {
    ({ reviewItemId } = await seedStatementConflictViaApi(page, workspaceId));
  } catch (err) {
    if (String(err).includes('e2e_shacl_violation_unavailable')) {
      test.skip(true, 'SHACL violation e2e helper only on data-e2e API');
    }
    throw err;
  }

  await page.goto(
    `/workspaces/${workspaceId}/review?reviewItem=${encodeURIComponent(reviewItemId)}`,
  );
  await expect(page).toHaveURL(new RegExp(`reviewItem=${encodeURIComponent(reviewItemId)}`));

  const unavailable = page.getByRole('heading', {
    name: /工作区不可用|Workspace unavailable/i,
  });
  if ((await unavailable.count()) > 0) {
    test.skip(true, 'review workspace requires graph_runtime');
  }

  const card = page.locator(`#review-item-${reviewItemId}`);
  await expect(card).toBeVisible({ timeout: 60_000 });
  await expect(card).toHaveClass(/ring-primary/);
  await expect(card.getByText(/SHACL|shacl/i)).toBeVisible();
});

test('viewing alerts clears unread badge but keeps episodes', async ({ page }) => {
  test.setTimeout(120_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);

  try {
    await seedGovernanceTrippedViaApi(page, workspaceId);
  } catch (err) {
    if (String(err).includes('e2e_governance_trip_unavailable')) {
      test.skip(true, 'governance e2e helper only on data-e2e API');
    }
    throw err;
  }

  await page.goto(`/workspaces/${workspaceId}/sources`);
  await page.getByTestId('basis-account-menu-trigger').click();
  await expect(page.getByTestId('workspace-account-alerts-badge')).toBeVisible({ timeout: 30_000 });

  await page.goto(`/workspaces/${workspaceId}/alerts`);
  await expect(page.locator('ul li').first()).toBeVisible({ timeout: 30_000 });
  await page.waitForResponse(
    (res) => res.url().includes('/alerts/mark-all-read') && res.ok(),
    { timeout: 30_000 },
  );

  await page.goto(`/workspaces/${workspaceId}/sources`);
  await expect
    .poll(async () => {
      await page.getByTestId('basis-account-menu-trigger').click();
      const count = await page.getByTestId('workspace-account-alerts-badge').count();
      await page.keyboard.press('Escape');
      return count;
    }, { timeout: 30_000 })
    .toBe(0);
});

test('dismiss all clears alerts list', async ({ page }) => {
  test.setTimeout(120_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);

  try {
    await seedGovernanceTrippedViaApi(page, workspaceId);
  } catch (err) {
    if (String(err).includes('e2e_governance_trip_unavailable')) {
      test.skip(true, 'governance e2e helper only on data-e2e API');
    }
    throw err;
  }

  await page.goto(`/workspaces/${workspaceId}/alerts`);
  await expect(page.locator('ul li').first()).toBeVisible({ timeout: 30_000 });
  await page.getByTestId('alerts-dismiss-all').click();
  await expect(page.getByText(/No active alerts|当前没有告警/i)).toBeVisible({
    timeout: 30_000,
  });
});

test('governance tripped alert shows detail fields', async ({ page }) => {
  test.setTimeout(120_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);

  let decisionId: string | null;
  try {
    ({ decisionId } = await seedGovernanceTrippedViaApi(page, workspaceId));
  } catch (err) {
    if (String(err).includes('e2e_governance_trip_unavailable')) {
      test.skip(true, 'governance e2e helper only on data-e2e API');
    }
    throw err;
  }

  await page.goto(`/workspaces/${workspaceId}/alerts`);
  await expect(page.locator('ul li').first()).toBeVisible({ timeout: 30_000 });
  if (decisionId) {
    await expect(page.getByText(new RegExp(decisionId))).toBeVisible({ timeout: 15_000 });
  }
});

test('governance tripped alert episode navigates detail to decisions', async ({ page }) => {
  test.setTimeout(120_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);

  let decisionId: string | null;
  try {
    ({ decisionId } = await seedGovernanceTrippedViaApi(page, workspaceId));
  } catch (err) {
    if (String(err).includes('e2e_governance_trip_unavailable')) {
      test.skip(true, 'governance e2e helper only on data-e2e API');
    }
    throw err;
  }
  if (!decisionId) {
    test.skip(true, 'governance trip did not record explorer decision_id');
  }

  await page.goto(`/workspaces/${workspaceId}/alerts`);
  await expect(page.locator('ul li').first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(new RegExp(decisionId!))).toBeVisible({ timeout: 15_000 });
  await page.getByRole('link', { name: /Open decisions|打开决策记录/i }).click();
  await expect(page).toHaveURL(/\/log/);
  await expect(page).toHaveURL(new RegExp(`graph_decision=${encodeURIComponent(decisionId!)}`));
});

test('governance tripped alert links to decisions tab', async ({ page }) => {
  test.setTimeout(120_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);

  let decisionId: string | null;
  try {
    ({ decisionId } = await seedGovernanceTrippedViaApi(page, workspaceId));
  } catch (err) {
    if (String(err).includes('e2e_governance_trip_unavailable')) {
      test.skip(true, 'governance e2e helper only on data-e2e API');
    }
    throw err;
  }
  if (!decisionId) {
    test.skip(true, 'governance trip did not record explorer decision_id');
  }

  await page.goto(`/workspaces/${workspaceId}/alerts`);
  await page.getByRole('link', { name: /Open decisions|打开决策记录/i }).click();
  await expect(page).toHaveURL(/\/log/);
  await expect(page).toHaveURL(new RegExp(`graph_decision=${encodeURIComponent(decisionId!)}`));
});

test('approve remember records governance decision deep link', async ({ page }) => {
  test.setTimeout(120_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);
  const fact = `E2E approve decision ${Date.now()}`;
  const { reviewItemId } = await proposeRememberViaApi(page, workspaceId, fact);

  await page.goto(`/workspaces/${workspaceId}/review?reviewItem=${encodeURIComponent(reviewItemId)}`);

  const unavailable = page.getByRole('heading', {
    name: /工作区不可用|Workspace unavailable/i,
  });
  if ((await unavailable.count()) > 0) {
    test.skip(true, 'review workspace requires graph_runtime');
  }

  const card = page.locator(`#review-item-${reviewItemId}`);
  await expect(card).toBeVisible({ timeout: 60_000 });
  await card.getByRole('button', { name: /Approve fact|批准记入/i }).click();

  const decisionLink = page.getByTestId('review-approve-decision-link');
  await expect(decisionLink).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId('review-item-decision-narrative').first()).toBeVisible({
    timeout: 30_000,
  });
  await decisionLink.click();
  await expect(page).toHaveURL(/\/log/);
  await expect(page).toHaveURL(/graph_decision=/);
});

test('resolved review deep link shows banner and decision links', async ({ page }) => {
  test.setTimeout(120_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);
  const fact = `E2E resolved deep link ${Date.now()}`;
  const { reviewItemId } = await proposeRememberViaApi(page, workspaceId, fact);

  await page.goto(`/workspaces/${workspaceId}/review?reviewItem=${encodeURIComponent(reviewItemId)}`);

  const unavailable = page.getByRole('heading', {
    name: /工作区不可用|Workspace unavailable/i,
  });
  if ((await unavailable.count()) > 0) {
    test.skip(true, 'review workspace requires graph_runtime');
  }

  const card = page.locator(`#review-item-${reviewItemId}`);
  await expect(card).toBeVisible({ timeout: 60_000 });
  await card.getByRole('button', { name: /Approve fact|批准记入/i }).click();
  await expect(page.getByTestId('review-approve-decision-link')).toBeVisible({ timeout: 30_000 });

  await page.reload();
  await expect(page.getByTestId('review-resolved-item-banner')).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId(/^review-resolved-decision-/).first()).toBeVisible();
  await expect(page.getByTestId('review-item-decision-narrative').first()).toBeVisible({
    timeout: 30_000,
  });
});

test('search graph tab shows temporal hint and link to graph workspace', async ({ page }) => {
  test.setTimeout(120_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);
  await page.goto(`/workspaces/${workspaceId}/search?scope=graph`);

  const unavailable = page.getByRole('heading', {
    name: /工作区不可用|Workspace unavailable/i,
  });
  if ((await unavailable.count()) > 0) {
    test.skip(true, 'graph search requires graph_runtime');
  }

  await expect(page.getByTestId('workspace-search-at')).toBeVisible({ timeout: 30_000 });
  await expect(
    page.getByText(/point-in-time|时点|playback|回放|scrubber|时间轴/i).first(),
  ).toBeVisible({ timeout: 30_000 });
  await page.getByTestId('workspace-search-open-graph').click();
  await expect(page).toHaveURL(new RegExp(`/workspaces/${workspaceId}/graph`));
});
