import { expect, test, type Page } from '@playwright/test';
import {
  createTestDataFactory,
  gotoAndWaitForAppReady,
  retryWithBackoff,
  waitForApiResponse
} from './support/stability';

type MutableState = {
  validateCalls: number;
  createCalls: number;
  updateCalls: number;
  savedWorkflowId: string;
  latestDefinition: Record<string, unknown>;
  runId: string;
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

async function mockWorkflowEditorApi(page: Page, namespace: string): Promise<MutableState> {
  const factory = createTestDataFactory(namespace);
  const state: MutableState = {
    validateCalls: 0,
    createCalls: 0,
    updateCalls: 0,
    savedWorkflowId: factory.nextId('wf_e2e_editor'),
    latestDefinition: {},
    runId: factory.nextId('run_e2e_editor')
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
      state.latestDefinition = definition;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ workflow: buildWorkflowRecord(definition, state.savedWorkflowId) })
      });
      return;
    }

    if (method === 'GET' && path.endsWith(`/workflow/${state.savedWorkflowId}`)) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildWorkflowRecord(state.latestDefinition, state.savedWorkflowId))
      });
      return;
    }

    if (method === 'PUT' && path.endsWith(`/workflow/${state.savedWorkflowId}`)) {
      state.updateCalls += 1;
      const payload = JSON.parse(request.postData() || '{}') as { updates?: Record<string, unknown> };
      const definition = payload.updates || {};
      state.latestDefinition = definition;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ workflow: buildWorkflowRecord(definition, state.savedWorkflowId) })
      });
      return;
    }

    if (method === 'GET' && path.endsWith(`/workflow/${state.savedWorkflowId}/runs`)) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ workflow_id: state.savedWorkflowId, runs: [], count: 0 })
      });
      return;
    }

    if (method === 'GET' && path.endsWith(`/workflow/runs/${state.runId}`)) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          run_id: state.runId,
          workflow_id: state.savedWorkflowId,
          workflow_version: 1,
          trigger: 'admin_console',
          status: 'completed',
          started_at: new Date().toISOString(),
          ended_at: new Date().toISOString(),
          duration_ms: 1,
          progress: 100,
          error: null,
          logs: [],
          node_statuses: {},
          node_attempts: {},
          node_outputs: {},
          node_timings_ms: {},
          variables: {},
          dag_levels: [],
          summary: { completed_nodes: 0, failed_nodes: 0, skipped_nodes: 0 }
        })
      });
      return;
    }

    if (method === 'GET' && path.endsWith(`/workflow/runs/${state.runId}/logs`)) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ run_id: state.runId, logs: [], count: 0 })
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
  test('应该能够校验并保存工作流', async ({ page }, testInfo) => {
    const state = await mockWorkflowEditorApi(page, testInfo.title);

    await gotoAndWaitForAppReady(page, '/#/workflows/editor', page.getByRole('button', { name: '保存' }));

    await expect(page.getByRole('button', { name: '校验' })).toBeVisible();
    await expect(page.getByRole('button', { name: '保存' })).toBeVisible();

    await waitForApiResponse(page, '/workflow/validate', async () => {
      await page.getByRole('button', { name: '校验' }).click();
    });
    await expect.poll(() => state.validateCalls).toBeGreaterThan(0);

    await waitForApiResponse(page, '/workflow', async () => {
      await page.getByRole('button', { name: '保存' }).click();
    });
    await expect.poll(() => state.createCalls).toBeGreaterThan(0);

    await expect(page.getByText('执行监控')).toHaveCount(1);
  });

  test('应该能够添加节点并触发自动布局', async ({ page }, testInfo) => {
    await mockWorkflowEditorApi(page, testInfo.title);

    await gotoAndWaitForAppReady(page, '/#/workflows/editor', page.getByRole('button', { name: '添加节点' }));

    await retryWithBackoff(
      async () => {
        await page.getByRole('button', { name: '添加节点' }).click();
        await page.getByText('处理节点').click();
      },
      { context: 'add node and select node type' }
    );

    await page.getByRole('button', { name: '自动布局' }).click();
    await expect(page.locator('.workflow-canvas')).toBeVisible();
  });

  test('应该能够复制并删除节点', async ({ page }, testInfo) => {
    await mockWorkflowEditorApi(page, testInfo.title);

    await gotoAndWaitForAppReady(page, '/#/workflows/editor', page.getByText('input_1').first());

    await page.getByText('input_1').first().click();
    await page.getByRole('button', { name: '复制节点' }).click();
    await expect(page.getByText('input_1_复制')).toBeVisible();

    await page.getByText('input_1_复制').first().click();
    await page.getByRole('button', { name: '删除节点' }).click();
    await expect(page.getByText('input_1_复制')).toHaveCount(0);
  });

  test('应该能够导入和导出工作流定义', async ({ page }, testInfo) => {
    const state = await mockWorkflowEditorApi(page, testInfo.title);

    await gotoAndWaitForAppReady(page, '/#/workflows/editor', page.getByRole('button', { name: '保存' }));

    const importedDefinition = {
      workflow_id: 'wf_imported_case',
      name: '导入流程A',
      description: 'imported by e2e',
      version: 1,
      nodes: [
        {
          node_id: 'input_a',
          kind: 'input',
          node_type: 'input.constant',
          params: { value: [10, 20] }
        }
      ],
      edges: []
    };

    await page.setInputFiles('input[type="file"]', {
      name: 'imported-workflow.json',
      mimeType: 'application/json',
      buffer: Buffer.from(JSON.stringify(importedDefinition), 'utf-8')
    });

    await expect(page.getByPlaceholder('工作流名称')).toHaveValue('导入流程A');

    await waitForApiResponse(page, '/workflow', async () => {
      await page.getByRole('button', { name: '保存' }).click();
    });
    await expect.poll(() => state.createCalls).toBeGreaterThan(0);
    await expect(page.getByRole('button', { name: '导出' })).toBeEnabled();

    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: '导出' }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toContain('导入流程A');
  });
});
