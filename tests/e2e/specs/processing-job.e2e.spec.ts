import { expect, test } from '@playwright/test';

import {
  defaultWorkspaceId,
  fetchLatestIngestJobId,
  ingestDocumentViaApi,
  registerFreshUser,
  seedProcessingFailedViaApi,
} from '../helpers';

test('sources job query opens processing history for job', async ({ page }) => {
  test.setTimeout(120_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);
  await ingestDocumentViaApi(page, workspaceId, 'Processing job deep link smoke.');
  const jobId = await fetchLatestIngestJobId(page, workspaceId);

  await page.goto(`/workspaces/${workspaceId}/sources`);
  await expect(page.locator('.basis-library-shell')).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId('sources-job-history')).toBeVisible();

  await page.goto(`/workspaces/${workspaceId}/processing?job=${encodeURIComponent(jobId)}`);
  await expect(page.locator('.basis-processing-view')).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId(`processing-job-detail-${jobId}`)).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByTestId(`processing-job-copy-link-${jobId}`)).toBeVisible();
  await expect(page.getByTestId(`processing-job-options-json-${jobId}`)).toBeVisible();
});

test('processing open in sources focuses document without process dialog', async ({ page }) => {
  test.setTimeout(120_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);
  await ingestDocumentViaApi(page, workspaceId, 'Processing sources deep link smoke.');
  const jobId = await fetchLatestIngestJobId(page, workspaceId);

  await page.goto(`/workspaces/${workspaceId}/processing?job=${encodeURIComponent(jobId)}`);
  await expect(page.getByTestId(`processing-job-detail-${jobId}`)).toBeVisible({
    timeout: 60_000,
  });

  await page.getByTestId(`processing-job-open-sources-${jobId}`).click();
  await expect(page).toHaveURL(/\/sources\?doc=/, { timeout: 30_000 });
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.locator('[id^="sources-doc-row-"]').first()).toHaveClass(/ring-primary/);
  await expect(page.getByTestId('workspace-document-timeline-panel')).toBeVisible({ timeout: 30_000 });
});

test('sources failed jobs badge opens processing failed filter', async ({ page }) => {
  test.setTimeout(120_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);

  try {
    await seedProcessingFailedViaApi(page, workspaceId);
  } catch (err) {
    if (String(err).includes('e2e_processing_failed_unavailable')) {
      test.skip(true, 'processing-failed e2e helper only on data-e2e API');
    }
    throw err;
  }

  await page.goto(`/workspaces/${workspaceId}/sources`);
  await expect(page.locator('.basis-library-shell')).toBeVisible({ timeout: 60_000 });
  await page.getByTestId('sources-job-history').click();
  await expect(page).toHaveURL(/filter=failed/, { timeout: 30_000 });
  await expect(page.getByRole('tab', { name: /Failed|失败/i })).toHaveAttribute(
    'data-state',
    'active',
  );
});

test('processing job links related alerts episode', async ({ page }) => {
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

  await page.goto(`/workspaces/${workspaceId}/processing?job=${encodeURIComponent(jobId)}`);
  await expect(page.getByTestId(`processing-job-detail-${jobId}`)).toBeVisible({
    timeout: 60_000,
  });
  await page.getByTestId(`processing-job-view-alerts-${jobId}`).click();
  await expect(page).toHaveURL(new RegExp(`episode=processing%3A${encodeURIComponent(jobId)}`));
  await expect(page.getByTestId(`alerts-episode-processing:${jobId}`)).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByTestId(`alerts-copy-episode-link-processing:${jobId}`)).toBeVisible();
});

test('processing filter query selects failed tab', async ({ page }) => {
  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);
  await page.goto(`/workspaces/${workspaceId}/processing?filter=failed`);
  await expect(page.locator('.basis-processing-view')).toBeVisible({ timeout: 60_000 });
  await expect(page).toHaveURL(/filter=failed/);
  await expect(page.getByRole('tab', { name: /Failed|失败/i })).toHaveAttribute(
    'data-state',
    'active',
  );
});

test('processing page loads job list', async ({ page }) => {
  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);

  await page.goto(`/workspaces/${workspaceId}/processing`);
  await expect(page.locator('.basis-processing-view')).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId('workspace-processing-view')).toBeVisible();
});
