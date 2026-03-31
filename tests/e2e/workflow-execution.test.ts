import { expect, test, type Page } from '@playwright/test';

type ExecutionState = {
  createCalls: number;
  executeCalls: number;
  workflowId: string;
  runId: string;
  detailFetchCount: number;
};

function buildWorkflowRecord(definition: Record<string, unknown>, workflowId: string) {
  const now = new Date().toISOString();
  return {
    workflow_id: workflowId,
    name: String(definition.name || '执行测试工作流'),
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

async function mockWorkflowExecutionApi(page: Page): Promise<ExecutionState> {
  const state: ExecutionState = {
    createCalls: 0,
    executeCalls: 0,
    workflowId: 'wf_e2e_execution',
    runId: 'run_e2e_execution',
    detailFetchCount: 0
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

    if (method === 'GET' && (path.endsWith('/workflow/templates') || path.endsWith('/workflow/marketplace'))) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(path.endsWith('/workflow/templates') ? { templates: [], count: 0 } : { items: [], count: 0 })
      });
      return;
    }

    if (method === 'POST' && path.endsWith('/workflow/validate')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ valid: true, node_count: 3, edge_count: 2, warnings: [] })
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
        body: JSON.stringify({ workflow: buildWorkflowRecord(definition, state.workflowId) })
      });
      return;
    }

    if (method === 'POST' && path.endsWith(`/workflow/${state.workflowId}/execute`)) {
      state.executeCalls += 1;
      const now = new Date().toISOString();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          run_id: state.runId,
          workflow_id: state.workflowId,
          workflow_version: 1,
          trigger: 'admin_console',
          status: 'queued',
          started_at: now,
          ended_at: null,
          duration_ms: null,
          progress: 0,
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

    if (method === 'GET' && path.endsWith(`/workflow/${state.workflowId}/runs`)) {
      const status = state.detailFetchCount > 0 ? 'completed' : 'running';
      const progress = state.detailFetchCount > 0 ? 100 : 60;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          workflow_id: state.workflowId,
          runs: [
            {
              run_id: state.runId,
              workflow_id: state.workflowId,
              workflow_version: 1,
              status,
              trigger: 'admin_console',
              started_at: new Date().toISOString(),
              ended_at: status === 'completed' ? new Date().toISOString() : null,
              duration_ms: status === 'completed' ? 120 : null,
              progress
            }
          ],
          count: 1
        })
      });
      return;
    }

    if (method === 'GET' && path.endsWith(`/workflow/runs/${state.runId}`)) {
      state.detailFetchCount += 1;
      const completed = state.detailFetchCount > 1;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          run_id: state.runId,
          workflow_id: state.workflowId,
          workflow_version: 1,
          trigger: 'admin_console',
          status: completed ? 'completed' : 'running',
          started_at: new Date().toISOString(),
          ended_at: completed ? new Date().toISOString() : null,
          duration_ms: completed ? 120 : null,
          progress: completed ? 100 : 60,
          error: null,
          logs: [],
          node_statuses: { input_1: 'completed', process_1: completed ? 'completed' : 'running' },
          node_attempts: {},
          node_outputs: {},
          node_timings_ms: {},
          variables: {},
          dag_levels: [],
          summary: { completed_nodes: completed ? 3 : 1, failed_nodes: 0, skipped_nodes: 0 }
        })
      });
      return;
    }

    if (method === 'GET' && path.endsWith(`/workflow/runs/${state.runId}/logs`)) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          run_id: state.runId,
          logs: [
            {
              ts: new Date().toISOString(),
              node_id: 'process_1',
              event: 'node_completed',
              message: 'done'
            }
          ],
          count: 1
        })
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

test.describe('工作流执行专项E2E', () => {
  test('应该能够触发执行并查看监控结果', async ({ page }) => {
    const state = await mockWorkflowExecutionApi(page);

    await page.goto('/#/workflows/editor');

    await page.getByRole('button', { name: '保存' }).click();
    await expect.poll(() => state.createCalls).toBeGreaterThan(0);

    await page.getByRole('button', { name: '执行' }).click();
    await expect.poll(() => state.executeCalls).toBeGreaterThan(0);

    await expect(page.getByText(state.runId).first()).toBeVisible();
    await expect(page.getByText('node_completed')).toBeVisible();
  });
});
