import { http } from './http';
import type {
  WorkflowCollaborationCursor,
  WorkflowComment,
  WorkflowCommentListResult,
  WorkflowCollaborator,
  WorkflowDefinition,
  WorkflowHealthSnapshot,
  WorkflowListItem,
  WorkflowMetrics,
  WorkflowNodeTypeCatalog,
  WorkflowNotificationListResult,
  WorkflowNotificationPreferences,
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
  enterprise_id?: string;
  owner?: string;
  assigned_to?: string;
}

export interface WorkflowTemplateCreatePayload {
  name: string;
  category?: string;
  tags?: string[];
  description?: string;
  shared?: boolean;
  workflow: WorkflowDefinition;
}

export interface WorkflowCommentListParams {
  page?: number;
  page_size?: number;
  sort?: 'asc' | 'desc';
}

export interface WorkflowCommentCreatePayload {
  content: string;
  parent_id?: string | null;
  mention_user_ids?: string[];
}

export interface WorkflowCommentUpdatePayload {
  content: string;
  mention_user_ids?: string[];
}

export interface WorkflowNotificationListParams {
  page?: number;
  page_size?: number;
  sort?: 'asc' | 'desc';
  unread_only?: boolean;
  types?: string[];
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

  async updateCollaborationCursor(
    workflowId: string,
    userId: string,
    position: {
      node_id?: string;
      x: number;
      y: number;
      selection?: Array<{ x: number; y: number; width: number; height: number }>;
    }
  ) {
    const { data } = await http.post<{
      workflow_id: string;
      cursor: WorkflowCollaborationCursor;
    }>(`/workflow/${workflowId}/collaboration/cursors`, {
      user_id: userId,
      position
    });
    return data;
  },

  async listCollaborationCursors(workflowId: string, activeSeconds = 30) {
    const { data } = await http.get<{
      workflow_id: string;
      cursors: WorkflowCollaborationCursor[];
      count: number;
    }>(`/workflow/${workflowId}/collaboration/cursors`, {
      params: { active_seconds: activeSeconds }
    });
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

  async listWorkflowTasks(workflowId: string, enterpriseId?: string) {
    const { data } = await http.get<{
      workflow_id: string;
      tasks: WorkflowRunItem[];
      count: number;
    }>(`/workflow/${workflowId}/tasks`, {
      params: { enterprise_id: enterpriseId }
    });
    return data;
  },

  async updateTaskAssignment(runId: string, payload: { assigned_to?: string; owner?: string }) {
    const { data } = await http.patch<{ task: WorkflowRunDetail }>(`/workflow/tasks/${runId}/assignment`, payload);
    return data.task;
  },

  async initiateTaskTransfer(runId: string, payload: { from_user_id: string; to_user_id: string }) {
    const { data } = await http.post<{ task: WorkflowRunDetail }>(`/workflow/tasks/${runId}/transfer`, payload);
    return data.task;
  },

  async confirmTaskTransfer(runId: string, payload: { receiver_user_id: string; accept: boolean }) {
    const { data } = await http.post<{ task: WorkflowRunDetail }>(
      `/workflow/tasks/${runId}/transfer/confirm`,
      payload
    );
    return data.task;
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
  },

  async listComments(workflowId: string, params: WorkflowCommentListParams = {}) {
    const { data } = await http.get<WorkflowCommentListResult>(`/workflow/${workflowId}/comments`, {
      params: {
        page: params.page ?? 1,
        page_size: params.page_size ?? 30,
        sort: params.sort ?? 'asc'
      }
    });
    return data;
  },

  async createComment(workflowId: string, payload: WorkflowCommentCreatePayload) {
    const { data } = await http.post<{ comment: WorkflowComment }>(`/workflow/${workflowId}/comments`, payload);
    return data.comment;
  },

  async updateComment(workflowId: string, commentId: string, payload: WorkflowCommentUpdatePayload) {
    const { data } = await http.put<{ comment: WorkflowComment }>(
      `/workflow/${workflowId}/comments/${commentId}`,
      payload
    );
    return data.comment;
  },

  async deleteComment(workflowId: string, commentId: string) {
    const { data } = await http.delete<{ deleted: boolean; comment_id: string }>(
      `/workflow/${workflowId}/comments/${commentId}`
    );
    return data;
  },

  async batchDeleteComments(workflowId: string, commentIds: string[]) {
    const { data } = await http.post<{ deleted_ids: string[]; count: number }>(
      `/workflow/${workflowId}/comments/batch-delete`,
      { comment_ids: commentIds }
    );
    return data;
  },

  async searchMentionCandidates(workflowId: string, keyword = '') {
    const { data } = await http.get<{ users: WorkflowCollaborator[]; count: number }>(
      `/workflow/${workflowId}/comments/mentions`,
      {
        params: {
          keyword
        }
      }
    );
    return data;
  },

  async listNotifications(workflowId: string, params: WorkflowNotificationListParams = {}) {
    const { data } = await http.get<WorkflowNotificationListResult>(`/workflow/${workflowId}/notifications`, {
      params: {
        page: params.page ?? 1,
        page_size: params.page_size ?? 30,
        sort: params.sort ?? 'desc',
        unread_only: params.unread_only ?? false,
        types: params.types?.join(',')
      }
    });
    return data;
  },

  async markNotificationRead(workflowId: string, notificationId: string) {
    const { data } = await http.post<{ notification_id: string; read: boolean }>(
      `/workflow/${workflowId}/notifications/${notificationId}/read`
    );
    return data;
  },

  async batchMarkNotificationsRead(workflowId: string, notificationIds: string[]) {
    const { data } = await http.post<{ count: number; notification_ids: string[] }>(
      `/workflow/${workflowId}/notifications/batch-read`,
      {
        notification_ids: notificationIds
      }
    );
    return data;
  },

  async markAllNotificationsRead(workflowId: string) {
    const { data } = await http.post<{ workflow_id: string; count: number }>(
      `/workflow/${workflowId}/notifications/read-all`
    );
    return data;
  },

  async getNotificationPreferences(workflowId: string) {
    const { data } = await http.get<WorkflowNotificationPreferences>(`/workflow/${workflowId}/notifications/preferences`);
    return data;
  },

  async updateNotificationPreferences(workflowId: string, payload: WorkflowNotificationPreferences) {
    const { data } = await http.put<WorkflowNotificationPreferences>(
      `/workflow/${workflowId}/notifications/preferences`,
      payload
    );
    return data;
  }
};
