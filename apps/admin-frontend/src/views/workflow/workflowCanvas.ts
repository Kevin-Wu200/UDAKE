import type { WorkflowNodeKind } from '../../types/workflow';

export interface WorkflowCanvasNodeData {
  kind: WorkflowNodeKind;
  nodeType: string;
  label: string;
  description?: string;
  enabled: boolean;
  params: Record<string, unknown>;
}

export const KIND_TEXT: Record<WorkflowNodeKind, string> = {
  input: '输入',
  process: '处理',
  output: '输出',
  control: '控制'
};

export const KIND_ACCENT: Record<WorkflowNodeKind, string> = {
  input: '#2563eb',
  process: '#0f766e',
  output: '#f97316',
  control: '#9333ea'
};
