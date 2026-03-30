import { expect, test, type Page } from '@playwright/test';

type MutableState = {
  validateCalls: number;
  createCalls: number;
  savedWorkflowId: string;
};

function buildWorkflowRecord(definition: Record<string, unknown>, workflowId: string) {
  const now = new Date().toISOString();
  return {
    workflow_id: workflowId,
    name: String(definition.name || 'E2E工作流'),
    description: String(definition.description || ''),
    current: {
      ...definition,
      workflow_id: workflowId,
      version: Number(definition.version || 1)
    },
    versions: [
      {
        version: Number(definition.version || 1),
        note: 'e2e_save',
        updated_at: now
      }
    ],
    collaborators: [],
    created_at: now,
    updated_at: now
  };
}

async function mockWorkflowEditorApi(page: Page): Promise<MutableState> {
  const state: MutableState = {
    validateCalls: 0,
    createCalls: 0,
    savedWorkflowId: 'wf_e2e_editor'
  };

  await page.addInitScript(() => {
    localStorage.setItem('admin_access_token', 'mock-admin-token');
  });

  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const method = request.method().toUpperCase();
    const url = new URL(request.url());
    const path = url.pathname;

    if (method === 'GET' && path.endsWith('/workflow/node-types')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          built_in: ['input.constant', 'process.transform', 'output.collect', 'control.condition'],
          custom: [],
          param_rules: {}
        })
      });
      return;
    }

    if (method === 'GET' && path.endsWith('/workflow/templates')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ templates: [], count: 0 })
      });
      return;
    }

    if (method === 'GET' && path.endsWith('/workflow/marketplace')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [], count: 0 })
      });
      return;
    }

    if (method === 'POST' && path.endsWith('/workflow/validate')) {
      state.validateCalls += 1;
      const payload = JSON.parse(request.postData() || '{}') as { definition?: { nodes?: unknown[]; edges?: unknown[] } };
      const nodes = Array.isArray(payload.definition?.nodes) ? payload.definition?.nodes?.length : 0;
      const edges = Array.isArray(payload.definition?.edges) ? payload.definition?.edges?.length : 0;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ valid: true, node_count: nodes, edge_count: edges, warnings: [] })
      });
      return;
    }

    if (method === 'POST' && path.endsWith('/workflow')) {
      state.createCalls += 1;
      const payload = JSON.parse(request.postData() || '{}') as { definition?: Record<string, unknown> };
      const definition = payload.definition || {};
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ workflow: buildWorkflowRecord(definition, state.savedWorkflowId) })
      });
      return;
    }

    await route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({ message: `unmocked endpoint: ${method} ${path}` })
    });
  });

  return state;
}

test.describe('工作流编辑器专项E2E', () => {
  test('应该能够校验并保存工作流', async ({ page }) => {
    const state = await mockWorkflowEditorApi(page);

    await page.goto('/#/workflows/editor');

    await expect(page.getByRole('button', { name: '校验' })).toBeVisible();
    await expect(page.getByRole('button', { name: '保存' })).toBeVisible();

    await page.getByRole('button', { name: '校验' }).click();
    await expect.poll(() => state.validateCalls).toBeGreaterThan(0);

    await page.getByRole('button', { name: '保存' }).click();
    await expect.poll(() => state.createCalls).toBeGreaterThan(0);

    await expect(page.getByText('执行监控')).toBeVisible();
  });

  test('应该能够添加节点并触发自动布局', async ({ page }) => {
    await mockWorkflowEditorApi(page);

    await page.goto('/#/workflows/editor');

    await page.getByRole('button', { name: '添加节点' }).click();
    await page.getByText('处理节点').click();

    await page.getByRole('button', { name: '自动布局' }).click();
    await expect(page.locator('.workflow-canvas')).toBeVisible();
  });
});
