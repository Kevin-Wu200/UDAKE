import type { WorkflowNodeKind } from '../../types/workflow';
export interface WorkflowCanvasNodeData {
  kind: WorkflowNodeKind;
  nodeType: string;
  label: string;
  description?: string;
  enabled: boolean;
  params: Record<string, unknown>;
}

export function getKindText(kind: WorkflowNodeKind, t: (k: string) => string): string {
  const map: Record<WorkflowNodeKind, string> = {
    input: t('input'),
    process: t('access'),
    output: t('output'),
    control: t('control')
  };
  return map[kind] || kind;
}

export const KIND_ACCENT: Record<WorkflowNodeKind, string> = {
  input: '#2563eb',
  process: '#0f766e',
  output: '#f97316',
  control: '#9333ea'
};
