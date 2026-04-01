export type WorkflowNodeKind = 'input' | 'process' | 'output' | 'control';

export interface WorkflowNodeDefinition {
  node_id: string;
  kind: WorkflowNodeKind;
  node_type: string;
  name?: string;
  description?: string;
  enabled?: boolean;
  params: Record<string, unknown>;
  retry?: {
    max_attempts?: number;
    delay_seconds?: number;
  };
}

export interface WorkflowEdgeDefinition {
  source: string;
  target: string;
  condition?: string;
}

export interface WorkflowDefinition {
  workflow_id: string;
  name: string;
  description?: string;
  version: number;
  nodes: WorkflowNodeDefinition[];
  edges: WorkflowEdgeDefinition[];
  variables?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  dag_levels?: string[][];
}

export interface WorkflowVersionItem {
  version: number;
  created_at: string;
  note: string;
}

export interface WorkflowCollaborator {
  user_id: string;
  role: string;
  display_name?: string;
}

export interface WorkflowCursorSelectionRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface WorkflowCollaborationCursor {
  user_id: string;
  node_id: string;
  x: number;
  y: number;
  selection: WorkflowCursorSelectionRect[];
  updated_at: string;
  color?: string;
  display_name?: string;
  avatar?: string;
}

export interface WorkflowRecord {
  workflow_id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  current: WorkflowDefinition;
  versions: WorkflowVersionItem[];
  collaborators: WorkflowCollaborator[];
}

export interface WorkflowListItem {
  workflow_id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  version: number;
  collaborator_count: number;
}

export interface WorkflowValidationResult {
  valid: boolean;
  workflow: WorkflowDefinition;
  dag_levels: string[][];
  node_count: number;
  edge_count: number;
}

export interface WorkflowRunSummary {
  completed_nodes: number;
  failed_nodes: number;
  skipped_nodes: number;
}

export type WorkflowRunStatus = 'queued' | 'running' | 'completed' | 'failed';

export interface WorkflowRunItem {
  run_id: string;
  workflow_id: string;
  workflow_version: number;
  status: WorkflowRunStatus;
  trigger: string;
  started_at: string;
  ended_at: string | null;
  duration_ms: number | null;
  progress: number;
}

export interface WorkflowRunDetail extends WorkflowRunItem {
  error: string | null;
  logs: WorkflowRunLog[];
  node_statuses: Record<string, string>;
  node_attempts: Record<string, number>;
  node_outputs: Record<string, unknown>;
  node_timings_ms: Record<string, number>;
  variables: Record<string, unknown>;
  dag_levels: string[][];
  summary: WorkflowRunSummary;
}

export interface WorkflowRunLog {
  ts: string;
  node_id: string;
  event: string;
  message: string;
}

export interface WorkflowMetrics {
  total_runs: number;
  success_runs: number;
  failed_runs: number;
  avg_duration_ms: number;
  last_updated_at: string;
}

export interface WorkflowSchedule {
  schedule_id: string;
  workflow_id: string;
  interval_seconds: number;
  enabled: boolean;
  trigger_payload: Record<string, unknown>;
  next_run_at: string;
  last_run_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface WorkflowTemplateRating {
  user_id: string;
  rating: number;
  comment: string;
  created_at: string;
}

export interface WorkflowTemplate {
  template_id: string;
  name: string;
  category: string;
  tags: string[];
  description: string;
  workflow: WorkflowDefinition;
  shared: boolean;
  rating_average: number;
  rating_count: number;
  usage_count: number;
  ratings: WorkflowTemplateRating[];
  created_at: string;
  updated_at: string;
}

export interface WorkflowTemplateRecommendation {
  score: number;
  template: WorkflowTemplate;
}

export interface WorkflowNodeTypeCatalog {
  built_in: string[];
  custom: string[];
  param_rules: Record<string, Record<string, unknown>>;
}

export interface WorkflowHealthSnapshot {
  status: string;
  module: string;
  workflow_count: number;
  template_count: number;
  run_count: number;
  schedule_count: number;
  scheduler_running: boolean;
}

export interface WorkflowCommentMention {
  user_id: string;
  display_name: string;
}

export interface WorkflowComment {
  comment_id: string;
  workflow_id: string;
  parent_id: string | null;
  root_id: string | null;
  depth: number;
  content: string;
  created_at: string;
  updated_at: string;
  deleted: boolean;
  author_id: string;
  author_name: string;
  author_avatar?: string;
  mention_users: WorkflowCommentMention[];
  reply_count: number;
}

export interface WorkflowCommentListResult {
  workflow_id: string;
  comments: WorkflowComment[];
  count: number;
  page: number;
  page_size: number;
  has_more: boolean;
}
