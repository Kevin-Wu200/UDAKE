import { http } from './http';
import type {
  WorkflowCollaborator,
  WorkflowDefinition,
  WorkflowHealthSnapshot,
  WorkflowListItem,
  WorkflowMetrics,
  WorkflowNodeTypeCatalog,
  WorkflowRecord,
  WorkflowRunDetail,
  WorkflowRunItem,
  WorkflowRunLog,
  WorkflowSchedule,
  WorkflowTemplate,
  WorkflowTemplateRecommendation,
  WorkflowValidationResult,
  WorkflowVersionItem
} from '../types/workflow';

export interface WorkflowExecutePayload {
  input_variables?: Record<string, unknown>;
  async?: boolean;
  debug?: boolean;
  trigger?: string;
}

export interface WorkflowTemplateCreatePayload {
  name: string;
  category?: string;
  tags?: string[];
  description?: string;
  shared?: boolean;
  workflow: WorkflowDefinition;
}

export const workflowService = {
  async getHealthSnapshot() {
    const { data } = await http.get<WorkflowHealthSnapshot>('/workflow/health');
    return data;
  },

  async getSchema() {
    const { data } = await http.get<Record<string, unknown>>('/workflow/schema');
    return data;
  },

  async listNodeTypes() {
    const { data } = await http.get<WorkflowNodeTypeCatalog>('/workflow/node-types');
    return data;
  },

  async validateDefinition(definition: WorkflowDefinition) {
    const { data } = await http.post<WorkflowValidationResult>('/workflow/validate', { definition });
    return data;
  },

  async createWorkflow(definition: WorkflowDefinition) {
    const { data } = await http.post<{ workflow: WorkflowRecord }>('/workflow', { definition });
    return data.workflow;
  },

  async listWorkflows() {
    const { data } = await http.get<{ workflows: WorkflowListItem[]; count: number }>('/workflow');
    return data;
  },

  async getWorkflow(workflowId: string) {
    const { data } = await http.get<WorkflowRecord>(`/workflow/${workflowId}`);
    return data;
  },

  async updateWorkflow(workflowId: string, updates: Partial<WorkflowDefinition>, note = 'update') {
    const { data } = await http.put<{ workflow: WorkflowRecord }>(`/workflow/${workflowId}`, {
      updates,
      note
    });
    return data.workflow;
  },

  async deleteWorkflow(workflowId: string) {
    const { data } = await http.delete<{ deleted: boolean; workflow_id: string }>(`/workflow/${workflowId}`);
    return data;
  },

  async listVersions(workflowId: string) {
    const { data } = await http.get<{
      workflow_id: string;
      versions: WorkflowVersionItem[];
      count: number;
    }>(`/workflow/${workflowId}/versions`);
    return data;
  },

  async rollbackWorkflow(workflowId: string, version: number) {
    const { data } = await http.post<{ workflow: WorkflowRecord }>(
      `/workflow/${workflowId}/rollback/${version}`
    );
    return data.workflow;
  },

  async exportWorkflow(workflowId: string) {
    const { data } = await http.get<{ definition: WorkflowDefinition }>(`/workflow/${workflowId}/export`);
    return data.definition;
  },

  async importWorkflow(definition: WorkflowDefinition, overwrite = false) {
    const { data } = await http.post<{ workflow: WorkflowRecord }>('/workflow/import', {
      definition,
      overwrite
    });
    return data.workflow;
  },

  async updateCollaborators(workflowId: string, collaborators: WorkflowCollaborator[]) {
    const { data } = await http.patch<{
      workflow_id: string;
      collaborators: WorkflowCollaborator[];
      count: number;
    }>(`/workflow/${workflowId}/collaborators`, { collaborators });
    return data;
  },

  async executeWorkflow(workflowId: string, payload: WorkflowExecutePayload) {
    const { data } = await http.post<WorkflowRunDetail>(`/workflow/${workflowId}/execute`, payload);
    return data;
  },

  async listWorkflowRuns(workflowId: string, limit = 100) {
    const { data } = await http.get<{
      workflow_id: string;
      runs: WorkflowRunItem[];
      count: number;
    }>(`/workflow/${workflowId}/runs`, {
      params: { limit }
    });
    return data;
  },

  async getRun(runId: string) {
    const { data } = await http.get<WorkflowRunDetail>(`/workflow/runs/${runId}`);
    return data;
  },

  async getRunLogs(runId: string) {
    const { data } = await http.get<{
      run_id: string;
      logs: WorkflowRunLog[];
      count: number;
    }>(`/workflow/runs/${runId}/logs`);
    return data;
  },

  async getPerformanceMetrics() {
    const { data } = await http.get<WorkflowMetrics>('/workflow/performance');
    return data;
  },

  async listTemplates(params?: { category?: string; shared_only?: boolean; limit?: number }) {
    const { data } = await http.get<{ templates: WorkflowTemplate[]; count: number }>('/workflow/templates', {
      params
    });
    return data;
  },

  async createTemplate(payload: WorkflowTemplateCreatePayload) {
    const { data } = await http.post<{ template: WorkflowTemplate }>('/workflow/templates', payload);
    return data.template;
  },

  async shareTemplate(templateId: string, shared = true) {
    const { data } = await http.post<{ template: WorkflowTemplate }>(
      `/workflow/templates/${templateId}/share`,
      {
        shared
      }
    );
    return data.template;
  },

  async rateTemplate(templateId: string, rating: number, userId = 'admin-console', comment = '') {
    const { data } = await http.post<{ template: WorkflowTemplate }>(
      `/workflow/templates/${templateId}/rate`,
      {
        rating,
        user_id: userId,
        comment
      }
    );
    return data.template;
  },

  async recommendTemplates(tags: string[], category?: string, limit = 5) {
    const { data } = await http.get<{ recommendations: WorkflowTemplateRecommendation[]; count: number }>(
      '/workflow/templates/recommend',
      {
        params: {
          tags: tags.join(','),
          category,
          limit
        }
      }
    );
    return data;
  },

  async instantiateTemplate(templateId: string, workflowName?: string) {
    const { data } = await http.post<{ workflow: WorkflowRecord }>(
      `/workflow/templates/${templateId}/instantiate`,
      {
        workflow_name: workflowName
      }
    );
    return data.workflow;
  },

  async getMarketplace(limit = 20) {
    const { data } = await http.get<{ items: WorkflowTemplate[]; count: number }>('/workflow/marketplace', {
      params: { limit }
    });
    return data;
  },

  async createSchedule(
    workflowId: string,
    payload: { interval_seconds: number; enabled?: boolean; trigger_payload?: Record<string, unknown> }
  ) {
    const { data } = await http.post<{ schedule: WorkflowSchedule }>(`/workflow/${workflowId}/schedules`, payload);
    return data.schedule;
  },

  async listSchedules(workflowId: string) {
    const { data } = await http.get<{
      workflow_id: string;
      schedules: WorkflowSchedule[];
      count: number;
    }>(`/workflow/${workflowId}/schedules`);
    return data;
  },

  async deleteSchedule(scheduleId: string) {
    const { data } = await http.delete<{ deleted: boolean; schedule_id: string }>(
      `/workflow/schedules/${scheduleId}`
    );
    return data;
  },

  async triggerSchedule(scheduleId: string) {
    const { data } = await http.post<{ run: WorkflowRunDetail }>(`/workflow/schedules/${scheduleId}/trigger`);
    return data.run;
  }
};
