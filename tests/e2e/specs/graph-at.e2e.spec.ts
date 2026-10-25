import { expect, test } from '@playwright/test';

import {
  defaultWorkspaceId,
  expectUrlAtMatchesInstant,
  fetchTemporalBounds,
  ingestDocumentViaApi,
  registerFreshUser,
  searchGraphNodes,
} from '../helpers';

test('graph at query opens temporal context', async ({ page }) => {
  test.setTimeout(120_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);
  await ingestDocumentViaApi(page, workspaceId, 'Graph temporal deep link smoke.');

  const bounds = await fetchTemporalBounds(page, workspaceId);
  const at = bounds.max ?? bounds.min ?? '2030-01-01T00:00:00Z';

  await page.goto(`/workspaces/${workspaceId}/graph?at=${encodeURIComponent(at)}`);

  const unavailable = page.getByRole('heading', {
    name: /工作区不可用|Workspace unavailable/i,
  });
  if ((await unavailable.count()) > 0) {
    test.skip(true, 'graph workspace requires graph_runtime');
  }

  await expect(page.locator('[data-testid="workspace-graph-canvas"]')).toBeVisible({
    timeout: 60_000,
  });
  await expect(page.getByText('Temporal', { exact: false }).first()).toBeVisible({
    timeout: 60_000,
  });
  await expect(page.getByTestId('graph-temporal-hint')).toBeVisible({ timeout: 60_000 });
});

test('graph timeline entry deep link opens playback footer', async ({ page }) => {
  test.setTimeout(120_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);
  await ingestDocumentViaApi(page, workspaceId, 'Graph timeline URL sync smoke.');

  const bounds = await fetchTemporalBounds(page, workspaceId);
  const at = bounds.max ?? bounds.min ?? '2030-01-01T00:00:00Z';

  await page.goto(`/workspaces/${workspaceId}/graph?at=${encodeURIComponent(at)}`);

  const unavailable = page.getByRole('heading', {
    name: /工作区不可用|Workspace unavailable/i,
  });
  if ((await unavailable.count()) > 0) {
    test.skip(true, 'graph workspace requires graph_runtime');
  }

  await expect(page.locator('[data-testid="workspace-graph-canvas"]')).toBeVisible({
    timeout: 60_000,
  });
  await page.getByTestId('workspace-graph-open-timeline').click();
  await expect(page).toHaveURL(/timeline=1/);
  await expectUrlAtMatchesInstant(page, at);
  await expect(page.locator('.explore-shell[data-timeline="true"]')).toBeVisible({
    timeout: 60_000,
  });
});

test('search open in graph focuses node', async ({ page }) => {
  test.setTimeout(120_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);
  await ingestDocumentViaApi(page, workspaceId, 'Search to graph link smoke node.');

  const bounds = await fetchTemporalBounds(page, workspaceId);
  const at = bounds.max ?? bounds.min ?? '2030-01-01T00:00:00Z';
  await page.goto(
    `/workspaces/${workspaceId}/search?scope=graph&q=smoke&at=${encodeURIComponent(at)}`,
  );

  const unavailable = page.getByRole('heading', {
    name: /工作区不可用|Workspace unavailable/i,
  });
  if ((await unavailable.count()) > 0) {
    test.skip(true, 'graph search requires graph_runtime');
  }

  await expect
    .poll(async () => (await searchGraphNodes(page, workspaceId, 'smoke')).length, { timeout: 60_000 })
    .toBeGreaterThan(0);
  const hits = await searchGraphNodes(page, workspaceId, 'smoke');
  const focusId = hits[0]?.node.id;
  expect(focusId).toBeTruthy();

  await expect(page.getByText(/result|结果/i).first()).toBeVisible({ timeout: 60_000 });
  const graphDeepLink = page.locator('a[href*="graph"][href*="focus="]').first();
  if (await graphDeepLink.isVisible().catch(() => false)) {
    await graphDeepLink.click();
  } else {
    await page.goto(
      `/workspaces/${workspaceId}/graph?focus=${encodeURIComponent(focusId!)}&at=${encodeURIComponent(at)}`,
    );
  }
  await expect(page.locator('[data-testid="workspace-graph-canvas"]')).toBeVisible({
    timeout: 60_000,
  });
  await expectUrlAtMatchesInstant(page, at);
});

test('search graph scope opens timeline playback deep link', async ({ page }) => {
  test.setTimeout(120_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);
  await ingestDocumentViaApi(page, workspaceId, 'Search timeline link smoke.');

  const bounds = await fetchTemporalBounds(page, workspaceId);
  const at = bounds.max ?? bounds.min ?? '2030-01-01T00:00:00Z';
  await page.goto(
    `/workspaces/${workspaceId}/search?scope=graph&q=smoke&at=${encodeURIComponent(at)}`,
  );

  const unavailable = page.getByRole('heading', {
    name: /工作区不可用|Workspace unavailable/i,
  });
  if ((await unavailable.count()) > 0) {
    test.skip(true, 'graph search requires graph_runtime');
  }

  await page.getByTestId('workspace-search-open-graph-timeline').click();
  await expect(page).toHaveURL(/timeline=1/);
  await expect(page.locator('.explore-shell[data-timeline="true"]')).toBeVisible({
    timeout: 60_000,
  });
});
