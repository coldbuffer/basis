import { expect, test, type Page } from '@playwright/test';

import { persistPlatformAdminIfApplicable, syncBrowserAuthToken } from './e2e-admin-session.js';
import { E2E_WORKSPACES_COLLECTION, e2eApiBaseUrl, e2eWorkspaceApiPath } from './api-v1-path.js';

export async function bearerToken(page: Page): Promise<string> {
  const token = await page.evaluate(() => localStorage.getItem('basis_token'));
  if (!token) {
    throw new Error('Missing basis_token after login');
  }
  return token;
}

export async function registerFreshUser(page: Page): Promise<{ email: string; password: string }> {
  const stamp = Date.now();
  const email = `e2e-${stamp}@e2e-${stamp}.invalid`;
  const password = 'password1xy';

  await page.goto('/');
  await page.evaluate(() => localStorage.clear());

  const reg = await page.request.post(`${e2eApiBaseUrl()}/api/v1/auth/register`, {
    data: {
      email,
      password,
      display_name: 'E2E User',
    },
  });
  expect(reg.ok(), `register failed: ${reg.status()} ${await reg.text()}`).toBeTruthy();
  const body = (await reg.json()) as { token: string };
  await persistPlatformAdminIfApplicable(page, { email, password }, body.token);
  await syncBrowserAuthToken(page, body.token);
  await page.goto('/workspaces');
  await expect(page).toHaveURL(/\/workspaces\//, { timeout: 60_000 });
  await expect
    .poll(
      async () => {
        const token = await page.evaluate(() => localStorage.getItem('basis_token'));
        if (!token) {
          return false;
        }
        const meRes = await page.request.get(`${e2eApiBaseUrl()}/api/v1/auth/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        return meRes.ok();
      },
      { timeout: 30_000 },
    )
    .toBe(true);

  return { email, password };
}

function isEditableRole(role: string | undefined): boolean {
  return role === 'admin' || role === 'owner' || role === 'editor';
}

export async function skipUnlessWorkspaceGraphWrite(page: Page, workspaceId: string): Promise<void> {
  const token = await bearerToken(page);
  const response = await page.request.get(e2eWorkspaceApiPath(workspaceId, 'capabilities'), {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(response.ok()).toBeTruthy();
  const body = (await response.json()) as { graph_write?: boolean };
  if (!body.graph_write) {
    test.skip(true, 'requires graph_runtime (graph_write)');
  }
}

export async function defaultWorkspaceId(page: Page): Promise<string> {
  const token = await bearerToken(page);
  const response = await page.request.get(`${e2eApiBaseUrl()}${E2E_WORKSPACES_COLLECTION}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(response.ok()).toBeTruthy();
  const body = (await response.json()) as {
    workspaces?: Array<{ id: string; my_role?: string }>;
  };
  const workspaces = body.workspaces ?? [];
  const editable = workspaces.find((ws) => isEditableRole(ws.my_role));
  if (editable?.id) {
    return editable.id;
  }

  const stamp = Date.now();
  const created = await page.request.post(`${e2eApiBaseUrl()}${E2E_WORKSPACES_COLLECTION}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    data: {
      name: `E2E workspace ${stamp}`,
      description: 'Playwright isolation',
      visibility: 'restricted',
    },
  });
  expect(created.ok()).toBeTruthy();
  const workspace = (await created.json()) as { id: string };
  if (!workspace.id) {
    throw new Error('POST /api/v1/workspaces did not return id');
  }
  return workspace.id;
}

export async function fetchGraphStats(
  page: Page,
  workspaceId: string,
): Promise<{ node_count: number; edge_count: number }> {
  const token = await bearerToken(page);
  const response = await page.request.get(e2eWorkspaceApiPath(workspaceId, 'graph/stats'), {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as { node_count: number; edge_count: number };
}

export async function searchGraphNodes(
  page: Page,
  workspaceId: string,
  query: string,
): Promise<Array<{ node: { id: string; content?: string; label?: string } }>> {
  const token = await bearerToken(page);
  const response = await page.request.post(e2eWorkspaceApiPath(workspaceId, 'graph/search'), {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    data: { query, limit: 20 },
  });
  expect(response.ok()).toBeTruthy();
  const body = (await response.json()) as {
    results?: Array<{ node: { id: string; content?: string; label?: string } }>;
  };
  return body.results ?? [];
}

export async function fetchFirstGraphNodeId(page: Page, workspaceId: string): Promise<string> {
  const token = await bearerToken(page);
  const response = await page.request.get(`${e2eWorkspaceApiPath(workspaceId, 'graph/nodes')}?limit=1`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(response.ok()).toBeTruthy();
  const body = (await response.json()) as { nodes?: Array<{ id: string }> };
  const id = body.nodes?.[0]?.id;
  if (!id) {
    throw new Error('No graph nodes available for lineage e2e');
  }
  return id;
}

export async function fetchProvenanceLineage(
  page: Page,
  workspaceId: string,
  nodeId: string,
): Promise<{ nodes: unknown[]; edges: unknown[] }> {
  const token = await bearerToken(page);
  const response = await page.request.get(
    `${e2eWorkspaceApiPath(workspaceId, 'provenance')}?node_id=${encodeURIComponent(nodeId)}`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as { nodes: unknown[]; edges: unknown[] };
}

/** Ingest via API (wait + extract) — reliable for graph/provenance e2e. */
export async function ingestDocumentViaApi(
  page: Page,
  workspaceId: string,
  text: string,
): Promise<void> {
  const token = await bearerToken(page);
  const response = await page.request.post(e2eWorkspaceApiPath(workspaceId, 'documents'), {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    data: {
      doc_id: `e2e-${Date.now()}`,
      text,
      wait: true,
      extract: true,
    },
  });
  expect(response.ok()).toBeTruthy();
  const stats = await fetchGraphStats(page, workspaceId);
  expect(stats.node_count).toBeGreaterThan(0);
}

/** Minimal document ingest (pattern extract) for graph projection smoke. */
export async function fetchLatestIngestJobId(page: Page, workspaceId: string): Promise<string> {
  const token = await bearerToken(page);
  const response = await page.request.get(`${e2eWorkspaceApiPath(workspaceId, 'ingest/jobs')}?limit=5`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(response.ok()).toBeTruthy();
  const body = (await response.json()) as { jobs?: Array<{ id: string }> };
  const id = body.jobs?.[0]?.id;
  if (!id) {
    throw new Error('No ingest jobs returned from GET .../ingest/jobs');
  }
  return id;
}

export async function fetchTemporalBounds(
  page: Page,
  workspaceId: string,
): Promise<{ min?: string; max?: string }> {
  const token = await bearerToken(page);
  const response = await page.request.get(e2eWorkspaceApiPath(workspaceId, 'temporal/bounds'), {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as { min?: string; max?: string };
}

export type ReasoningRunResult = {
  facts_source?: string;
  inferred_facts?: string[];
  derived_facts_persisted?: { created?: number };
};

export async function runReasoningViaApi(
  page: Page,
  workspaceId: string,
  options: {
    rules: string[];
    facts?: string[];
    applyToGraph?: boolean;
  },
): Promise<ReasoningRunResult> {
  const token = await bearerToken(page);
  const data: Record<string, unknown> = {
    rules: options.rules,
    mode: 'forward',
    apply_to_graph: options.applyToGraph ?? false,
  };
  if (options.facts !== undefined) {
    data.facts = options.facts;
  }
  const response = await page.request.post(e2eWorkspaceApiPath(workspaceId, 'reasoning/run'), {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    data,
  });
  if (response.status() === 503) {
    throw new Error('graph_runtime_unavailable');
  }
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as ReasoningRunResult;
}

export async function runReasoningApplyViaApi(
  page: Page,
  workspaceId: string,
  facts: string[],
  rules: string[],
): Promise<{ derived_facts_persisted?: { created?: number } }> {
  return runReasoningViaApi(page, workspaceId, { facts, rules, applyToGraph: true });
}

export async function createWorkspaceWithDemoImport(page: Page): Promise<string> {
  const token = await bearerToken(page);
  const stamp = Date.now();
  const created = await page.request.post(`${e2eApiBaseUrl()}${E2E_WORKSPACES_COLLECTION}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    data: {
      name: `E2E demo ${stamp}`,
      description: 'Playwright demo pack',
      visibility: 'restricted',
      import_demo_data: true,
    },
  });
  if (created.status() === 403) {
    throw new Error('demo_workspace_import_disabled');
  }
  expect(created.ok()).toBeTruthy();
  const workspace = (await created.json()) as { id: string };
  if (!workspace.id) {
    throw new Error('POST /api/v1/workspaces did not return id');
  }
  return workspace.id;
}

/** Seed governance.tripped + graph decision (Playwright data-e2e API only). */
export async function seedGovernanceTrippedViaApi(
  page: Page,
  workspaceId: string,
): Promise<{ decisionId: string | null }> {
  const token = await bearerToken(page);
  const response = await page.request.post(e2eWorkspaceApiPath(workspaceId, '_e2e/governance-trip'), {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (response.status() === 404) {
    throw new Error('e2e_governance_trip_unavailable');
  }
  expect(response.ok()).toBeTruthy();
  const body = (await response.json()) as { decision_id?: string | null };
  return { decisionId: body.decision_id ?? null };
}

/** Seed processing.failed alert with job_id (Playwright data-e2e API only). */
export async function seedProcessingFailedViaApi(
  page: Page,
  workspaceId: string,
): Promise<{ jobId: string; docId: string }> {
  const token = await bearerToken(page);
  const response = await page.request.post(e2eWorkspaceApiPath(workspaceId, '_e2e/processing-failed'), {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (response.status() === 404) {
    throw new Error('e2e_processing_failed_unavailable');
  }
  expect(response.ok()).toBeTruthy();
  const body = (await response.json()) as { job_id?: string; doc_id?: string };
  if (!body.job_id || !body.doc_id) {
    throw new Error('e2e processing-failed did not return job_id/doc_id');
  }
  return { jobId: body.job_id, docId: body.doc_id };
}

/** Seed sync_failed alert with source_id (Playwright data-e2e API only). */
export async function seedSyncFailedViaApi(
  page: Page,
  workspaceId: string,
): Promise<{ sourceId: string }> {
  const token = await bearerToken(page);
  const response = await page.request.post(e2eWorkspaceApiPath(workspaceId, '_e2e/sync-failed'), {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (response.status() === 404) {
    throw new Error('e2e_sync_failed_unavailable');
  }
  expect(response.ok()).toBeTruthy();
  const body = (await response.json()) as { source_id?: string };
  if (!body.source_id) {
    throw new Error('e2e sync-failed did not return source_id');
  }
  return { sourceId: body.source_id };
}

/** Seed SHACL violation review item via mapped statements (Playwright data-e2e API only). */
export async function seedStatementConflictViaApi(
  page: Page,
  workspaceId: string,
): Promise<{ reviewItemId: string; surfacePhrase: string }> {
  const token = await bearerToken(page);
  const response = await page.request.post(e2eWorkspaceApiPath(workspaceId, '_e2e/shacl-violation'), {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (response.status() === 404) {
    throw new Error('e2e_shacl_violation_unavailable');
  }
  expect(response.ok()).toBeTruthy();
  const body = (await response.json()) as {
    review_item_id?: string | null;
    surface_phrase?: string;
  };
  if (!body.review_item_id) {
    throw new Error('e2e statement-conflict did not create review_item_id');
  }
  return {
    reviewItemId: body.review_item_id,
    surfacePhrase: body.surface_phrase ?? '',
  };
}

export async function seedOntologyProposalViaApi(
  page: Page,
  workspaceId: string,
): Promise<{ proposalId: string; summary: string }> {
  const token = await bearerToken(page);
  const response = await page.request.post(e2eWorkspaceApiPath(workspaceId, '_e2e/ontology-proposal'), {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (response.status() === 404) {
    throw new Error('e2e_ontology_proposal_unavailable');
  }
  expect(response.ok()).toBeTruthy();
  const body = (await response.json()) as { proposal_id?: string; summary?: string };
  if (!body.proposal_id) {
    throw new Error('e2e ontology-proposal did not return proposal_id');
  }
  return {
    proposalId: body.proposal_id,
    summary: body.summary ?? '',
  };
}

/** Ensures the user belongs to an org (creates a workspace + org when needed). */
export async function ensureUserOrganization(page: Page): Promise<string> {
  const token = await bearerToken(page);
  const api = e2eApiBaseUrl();
  let orgId: string | undefined;
  await expect
    .poll(async () => {
      const mine = await page.request.get(`${api}/api/v1/orgs/mine`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!mine.ok()) return '';
      const body = (await mine.json()) as { organizations?: Array<{ id: string }> };
      orgId = body.organizations?.[0]?.id;
      if (orgId) return orgId;
      await defaultWorkspaceId(page);
      return '';
    }, { timeout: 60_000 })
    .not.toBe('');
  return orgId!;
}

export async function approveReviewItemViaApi(
  page: Page,
  workspaceId: string,
  reviewItemId: string,
): Promise<{ decisionId?: string }> {
  const token = await bearerToken(page);
  const response = await page.request.post(
    e2eWorkspaceApiPath(workspaceId, `review/items/${reviewItemId}/approve`),
    {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      data: { rationale: 'E2E approve' },
    },
  );
  expect(response.ok(), `approve failed: ${response.status()} ${await response.text()}`).toBeTruthy();
  const body = (await response.json()) as { decision_id?: string | null };
  return { decisionId: body.decision_id ?? undefined };
}

export async function rebuildGraphProjectionViaApi(page: Page, workspaceId: string): Promise<void> {
  const token = await bearerToken(page);
  const response = await page.request.post(e2eWorkspaceApiPath(workspaceId, 'graph/rebuild'), {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(response.ok(), `graph rebuild failed: ${response.status()} ${await response.text()}`).toBeTruthy();
}

/** URL `at` query may use Z or offset; compare instants. */
export async function expectUrlAtMatchesInstant(
  page: import('@playwright/test').Page,
  atIso: string,
): Promise<void> {
  const expectedMs = Date.parse(atIso);
  expect(Number.isFinite(expectedMs), `invalid at ISO: ${atIso}`).toBeTruthy();
  await expect
    .poll(() => {
      try {
        const atParam = new URL(page.url()).searchParams.get('at');
        if (!atParam) return false;
        const actualMs = Date.parse(atParam);
        return Number.isFinite(actualMs) && actualMs === expectedMs;
      } catch {
        return false;
      }
    }, { timeout: 15_000 })
    .toBe(true);
}

export async function proposeRememberViaApi(
  page: Page,
  workspaceId: string,
  content: string,
): Promise<{ reviewItemId: string }> {
  const token = await bearerToken(page);
  const response = await page.request.post(e2eWorkspaceApiPath(workspaceId, 'remember/proposals'), {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    data: { content },
  });
  expect(response.ok()).toBeTruthy();
  const body = (await response.json()) as { review_item_id?: string };
  if (!body.review_item_id) {
    throw new Error('POST /remember/proposals did not return review_item_id');
  }
  return { reviewItemId: body.review_item_id };
}

export async function ingestPasteText(page: Page, workspaceId: string, text: string): Promise<void> {
  await Promise.all([
    page.waitForResponse(
      (response) =>
        response.url().includes('/capabilities') &&
        response.request().method() === 'GET' &&
        response.ok(),
    ),
    page.goto(`/workspaces/${workspaceId}/sources`),
  ]);
  await expect(page.locator('.basis-library-shell')).toBeVisible({ timeout: 60_000 });
  const addDoc = page.getByRole('button', { name: /添加文档|Add document/i }).first();
  await expect(addDoc).toBeVisible({ timeout: 60_000 });
  await addDoc.click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('tab', { name: /粘贴文本|Paste text/i }).click();
  await dialog.locator('#add-text').fill(text);
  await dialog.getByRole('checkbox').check();
  await dialog.getByRole('button', { name: /^保存$|^Save$/i }).click();
  await expect(page.getByText(text, { exact: false })).toBeVisible({ timeout: 90_000 });
  await expect(page.getByText(/就绪|Ready/i).first()).toBeVisible({ timeout: 90_000 });
  const stats = await fetchGraphStats(page, workspaceId);
  expect(stats.node_count).toBeGreaterThan(0);
}

export async function waitForLedgerSurfacePhrases(
  page: Page,
  workspaceId: string,
  minCount = 1,
): Promise<string[]> {
  const token = await bearerToken(page);
  let phrases: string[] = [];
  await expect
    .poll(
      async () => {
        const response = await page.request.get(
          e2eWorkspaceApiPath(workspaceId, 'ledger/surface-phrases'),
          { headers: { Authorization: `Bearer ${token}` } },
        );
        if (!response.ok()) {
          return false;
        }
        const body = (await response.json()) as { phrases?: string[] };
        phrases = body.phrases ?? [];
        return phrases.length >= minCount;
      },
      { timeout: 120_000 },
    )
    .toBe(true);
  return phrases;
}

export async function createProposedRelationMappingViaUi(
  page: Page,
  workspaceId: string,
  signature: string,
  targetUri: string,
): Promise<void> {
  await page.goto(`/workspaces/${workspaceId}/mappings`);
  await page.getByRole('button', { name: /New mapping|新建映射/i }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();

  const phraseInput = dialog.getByPlaceholder(/Search relation words|搜索关系词/i);
  await phraseInput.click();
  await phraseInput.fill(signature);
  await dialog.getByRole('option', { name: signature, exact: true }).click();

  const uriInput = dialog.getByPlaceholder(/Search properties|搜索属性/i);
  await uriInput.fill(targetUri);

  await dialog.getByRole('button', { name: /Submit proposal|提交提案/i }).click();
  await expect(dialog).toBeHidden({ timeout: 30_000 });
  await expect(page.locator('tr').filter({ hasText: signature })).toBeVisible({ timeout: 30_000 });
}

export async function waitForOntologyMappingReviewItemId(
  page: Page,
  workspaceId: string,
  signature: string,
): Promise<string> {
  const token = await bearerToken(page);
  let itemId = '';
  await expect
    .poll(
      async () => {
        const response = await page.request.get(e2eWorkspaceApiPath(workspaceId, 'review/items'), {
          headers: { Authorization: `Bearer ${token}` },
          params: { kind: 'ontology_mapping' },
        });
        if (!response.ok()) {
          return false;
        }
        const body = (await response.json()) as {
          items?: Array<{ id: string; payload?: { signature?: string } }>;
        };
        const hit = (body.items ?? []).find((item) => item.payload?.signature === signature);
        itemId = hit?.id ?? '';
        return Boolean(itemId);
      },
      { timeout: 60_000 },
    )
    .toBe(true);
  return itemId;
}

export async function skipIfReviewWorkspaceUnavailable(page: Page): Promise<void> {
  const unavailable = page.getByRole('heading', {
    name: /工作区不可用|Workspace unavailable/i,
  });
  if ((await unavailable.count()) > 0) {
    test.skip(true, 'review workspace requires graph_runtime');
  }
}
