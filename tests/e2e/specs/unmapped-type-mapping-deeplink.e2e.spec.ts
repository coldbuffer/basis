import { expect, test } from '@playwright/test';

import {
  defaultWorkspaceId,
  expectNoOpenUnmappedEntityTypeReviews,
  registerFreshUser,
  seedUnmappedEntityTypeViaApi,
  submitMappingsCreateDialog,
} from '../helpers.js';

test('review unmapped type opens prefilled create type mapping dialog', async ({ page }) => {
  test.setTimeout(120_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);

  let seeded: { reviewItemId: string; label: string };
  try {
    seeded = await seedUnmappedEntityTypeViaApi(page, workspaceId);
  } catch (err) {
    if (err instanceof Error && err.message === 'e2e_unmapped_entity_type_unavailable') {
      test.skip(true, 'unmapped entity type e2e helper requires data-e2e server');
    }
    throw err;
  }

  await page.goto(`/workspaces/${workspaceId}/review`);

  const unavailable = page.getByRole('heading', {
    name: /工作区不可用|Workspace unavailable/i,
  });
  if ((await unavailable.count()) > 0) {
    test.skip(true, 'review workspace requires graph_runtime');
  }

  const qualityLink = page.getByTestId(`review-quality-link-${seeded.reviewItemId}`);
  await expect(qualityLink).toBeVisible({ timeout: 60_000 });
  await qualityLink.click();

  const dialog = page.getByTestId('mappings-create-dialog');
  await expect(dialog).toBeVisible({ timeout: 30_000 });
  await expect(dialog.getByText(seeded.label, { exact: true })).toBeVisible();
});

test('review unmapped type with L1 hint includes typeMappingUri in navigation', async ({ page }) => {
  test.setTimeout(120_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);

  let seeded: { reviewItemId: string; label: string; l1Uri?: string | null };
  try {
    seeded = await seedUnmappedEntityTypeViaApi(page, workspaceId, { withL1Hint: true });
  } catch (err) {
    if (err instanceof Error && err.message === 'e2e_unmapped_entity_type_unavailable') {
      test.skip(true, 'unmapped entity type e2e helper requires data-e2e server');
    }
    throw err;
  }
  expect(seeded.l1Uri).toBeTruthy();

  await page.goto(`/workspaces/${workspaceId}/review`);
  const qualityLink = page.getByTestId(`review-quality-link-${seeded.reviewItemId}`);
  await expect(qualityLink).toBeVisible({ timeout: 60_000 });
  await qualityLink.click();

  await expect(page).toHaveURL(/typeMappingUri=/, { timeout: 30_000 });
  await expect(page.getByTestId('mappings-create-dialog')).toBeVisible({ timeout: 30_000 });
});

test('confirming class mapping from unmapped review closes the review item', async ({ page }) => {
  test.setTimeout(180_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);

  let seeded: { reviewItemId: string; label: string; l1Uri?: string | null };
  try {
    seeded = await seedUnmappedEntityTypeViaApi(page, workspaceId, { withL1Hint: true });
  } catch (err) {
    if (err instanceof Error && err.message === 'e2e_unmapped_entity_type_unavailable') {
      test.skip(true, 'unmapped entity type e2e helper requires data-e2e server');
    }
    throw err;
  }

  await page.goto(`/workspaces/${workspaceId}/review`);
  const qualityLink = page.getByTestId(`review-quality-link-${seeded.reviewItemId}`);
  await expect(qualityLink).toBeVisible({ timeout: 60_000 });
  await qualityLink.click();

  await submitMappingsCreateDialog(page, {
    targetUri: seeded.l1Uri ?? 'http://example.org/e2e#Class',
  });

  const mappingRow = page.locator('tr').filter({ hasText: seeded.label });
  await expect(mappingRow).toBeVisible({ timeout: 30_000 });
  await mappingRow.getByRole('button', { name: /Confirm|确认/i }).click();

  await expectNoOpenUnmappedEntityTypeReviews(page, workspaceId);
});
