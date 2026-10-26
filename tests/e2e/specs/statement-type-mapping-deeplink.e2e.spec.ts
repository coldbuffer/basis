import { expect, test } from '@playwright/test';

import { defaultWorkspaceId, registerFreshUser } from '../helpers.js';

test('semantic alignment deep link opens prefilled type mapping dialog', async ({ page }) => {
  test.setTimeout(90_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);
  const label = 'e2e_type_label';

  await page.goto(
    `/workspaces/${workspaceId}/ontology?tab=statement&typeMappingLabel=${encodeURIComponent(label)}`,
  );

  const panel = page.getByTestId('mappings-workspace-panel');
  await expect(panel).toBeVisible({ timeout: 60_000 });

  const dialog = page.getByTestId('mappings-create-dialog');
  await expect(dialog).toBeVisible({ timeout: 30_000 });
  await expect(dialog.getByText(label, { exact: true })).toBeVisible();
});
