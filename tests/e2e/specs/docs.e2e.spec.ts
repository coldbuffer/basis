import { expect, test } from '@playwright/test';

test.use({
  locale: 'en-US',
  viewport: { width: 1536, height: 960 },
});

test('docs sidebar lists getting started and operations pages together', async ({ page }) => {
  await page.goto('/docs');

  const sidebar = page.locator('aside').getByTestId('docs-sidebar');
  await expect(sidebar).toBeVisible({ timeout: 30_000 });
  await expect(sidebar.getByRole('link', { name: 'Quickstart' })).toBeVisible();
  await expect(sidebar.getByRole('link', { name: 'Self-host' })).toBeVisible();
  await expect(page.getByTestId('docs-zone-tabs')).toHaveCount(0);
});

test('docs overview links navigate into the reading path', async ({ page }) => {
  await page.goto('/docs');

  const article = page.locator('[data-doc-article]');
  await expect(article.getByRole('link', { name: 'Connectors (Basis)' })).toHaveAttribute(
    'href',
    '/docs/connectors-basis',
  );

  await article.getByRole('link', { name: 'Quickstart' }).click();

  await expect(page).toHaveURL(/\/docs\/quickstart$/);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Quickstart');
});

test('docs search finds pages by title', async ({ page }) => {
  await page.goto('/docs');
  await page.getByTestId('docs-search-open').click();
  const input = page.getByTestId('docs-search-input');
  await expect(input).toBeVisible();
  await input.fill('workspace reset');
  await page.getByRole('option', { name: /Export pack and workspace reset/i }).click();
  await expect(page).toHaveURL(/\/docs\/guide-export-backup$/);
});

test('docs MCP tools index renders generated tables', async ({ page }) => {
  await page.goto('/docs/mcp-tools');

  await expect(page.getByRole('heading', { level: 1 })).toHaveText('MCP tools index');
  const article = page.locator('[data-doc-article]');
  await expect(article.getByRole('heading', { name: 'Knowledge & ledger' })).toBeVisible();
  await expect(article.locator('code').filter({ hasText: 'search_chunks' }).first()).toBeVisible();
});

test('docs connector runtime page loads from sidebar', async ({ page }) => {
  await page.goto('/docs/connectors-basis');

  const sidebar = page.getByTestId('docs-sidebar');
  await expect(sidebar.getByRole('link', { name: 'Connectors (Basis)' })).toHaveAttribute(
    'aria-current',
    'page',
  );
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(
    'Basis connector runtime (BOCP host)',
  );
});

test('BOCP pager advances to the connector runtime page', async ({ page }) => {
  await page.goto('/docs/bocp');

  const pager = page.getByRole('navigation', {
    name: 'Previous and next documentation pages',
  });
  await pager.getByRole('link', { name: /Connectors \(Basis\)/ }).click();

  await expect(page).toHaveURL(/\/docs\/connectors-basis$/);
});

test('unknown docs path renders a 404 without redirecting', async ({ page }) => {
  await page.goto('/docs/does-not-exist/extra');

  await expect(page).toHaveURL(/\/docs\/does-not-exist\/extra$/);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Page not found');
  await expect(page.getByText('/docs/does-not-exist/extra')).toBeVisible();

  await page.getByRole('link', { name: 'Documentation overview' }).click();

  await expect(page).toHaveURL(/\/docs$/);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Basis developer documentation');
});
