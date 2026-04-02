import { expect, test, type Page } from '@playwright/test';
import {
  createTestDataFactory,
  gotoAndWaitForAppReady,
  waitForApiResponse
} from './support/stability';

type TemplateState = {
  recommendationCalls: number;
  instantiateCalls: number;
};

async function mockWorkflowTemplateApi(page: Page): Promise<TemplateState> {
  const state: TemplateState = {
    recommendationCalls: 0,
    instantiateCalls: 0
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
        body: JSON.stringify({
          templates: [
            {
              template_id: 'tpl_e2e_1',
              name: '数据清洗模板',
              category: 'data',
              tags: ['采样', '清洗'],
              description: 'E2E模板',
              workflow: {
                workflow_id: 'wf_tpl_inner',
                name: '模板流程',
                version: 1,
                description: 'from template',
                nodes: [
                  {
                    node_id: 'input_1',
                    kind: 'input',
                    node_type: 'input.constant',
                    params: { value: [1, 2, 3] }
                  }
                ],
                edges: []
              },
              shared: true,
              rating_average: 4.8,
              rating_count: 10,
              usage_count: 25,
              ratings: [],
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString()
            }
          ],
          count: 1
        })
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

    if (method === 'GET' && path.endsWith('/workflow/templates/recommend')) {
      state.recommendationCalls += 1;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          recommendations: [
            {
              score: 0.91,
              reason: '标签匹配',
              template: {
                template_id: 'tpl_e2e_2',
                name: '推荐模板',
                category: 'data',
                tags: ['采样'],
                description: '推荐结果',
                workflow: {
                  workflow_id: 'wf_tpl_recommend',
                  name: '推荐流程',
                  version: 1,
                  description: 'recommended',
                  nodes: [],
                  edges: []
                },
                shared: true,
                rating_average: 4.6,
                rating_count: 3,
                usage_count: 8,
                ratings: [],
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString()
              }
            }
          ],
          count: 1
        })
      });
      return;
    }

    if (method === 'POST' && path.endsWith('/workflow/templates/tpl_e2e_1/instantiate')) {
      state.instantiateCalls += 1;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          workflow: {
            workflow_id: 'wf_from_template',
            name: '模板实例',
            description: 'instantiated',
            current: {
              workflow_id: 'wf_from_template',
              name: '模板实例',
              version: 1,
              description: 'instantiated',
              nodes: [],
              edges: []
            },
            versions: [],
            collaborators: [],
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          }
        })
      });
      return;
    }

    if (method === 'POST' && path.endsWith('/workflow/templates/tpl_e2e_2/instantiate')) {
      state.instantiateCalls += 1;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          workflow: {
            workflow_id: 'wf_from_recommend',
            name: '推荐模板实例',
            description: 'instantiated from recommendation',
            current: {
              workflow_id: 'wf_from_recommend',
              name: '推荐模板实例',
              version: 1,
              description: 'instantiated from recommendation',
              nodes: [],
              edges: []
            },
            versions: [],
            collaborators: [],
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          }
        })
      });
      return;
    }

    if (method === 'GET' && path.endsWith('/workflow/wf_from_template')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          workflow_id: 'wf_from_template',
          name: '模板实例',
          description: 'instantiated',
          current: {
            workflow_id: 'wf_from_template',
            name: '模板实例',
            version: 1,
            description: 'instantiated',
            nodes: [],
            edges: []
          },
          versions: [],
          collaborators: [],
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        })
      });
      return;
    }

    if (method === 'POST' && path.endsWith('/workflow/validate')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ valid: true, node_count: 1, edge_count: 0, warnings: [] })
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

test.describe('工作流模板专项E2E', () => {
  test('应该能够浏览模板并应用到编辑器', async ({ page }, testInfo) => {
    createTestDataFactory(testInfo.title);
    await mockWorkflowTemplateApi(page);

    await gotoAndWaitForAppReady(page, '/#/workflows/editor', page.getByText('数据清洗模板'));

    await expect(page.getByText('数据清洗模板')).toBeVisible();
    await page.getByRole('button', { name: '应用' }).first().click();

    await expect(page.getByPlaceholder('工作流名称')).toHaveValue(/数据清洗模板_编辑副本/);
  });

  test('应该能够请求模板推荐并实例化模板', async ({ page }, testInfo) => {
    createTestDataFactory(testInfo.title);
    const state = await mockWorkflowTemplateApi(page);

    await gotoAndWaitForAppReady(page, '/#/workflows/editor', page.getByRole('button', { name: '推荐' }));

    await page.getByPlaceholder('推荐标签（逗号分隔）').fill('采样,插值');
    await waitForApiResponse(page, '/workflow/templates/recommend', async () => {
      await page.getByRole('button', { name: '推荐' }).click();
    });
    await expect.poll(() => state.recommendationCalls).toBeGreaterThan(0);

    await waitForApiResponse(page, '/instantiate', async () => {
      await page.getByRole('button', { name: '实例化' }).first().click();
    });
    await expect.poll(() => state.instantiateCalls).toBeGreaterThan(0);
  });
});
