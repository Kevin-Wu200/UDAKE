<template>
  <div class="workflow-editor-page">
    <WorkflowToolbar
      :loading="loading"
      :has-workflow="Boolean(persistedWorkflowId)"
      :can-execute="Boolean(persistedWorkflowId || nodes.length)"
      @save="saveWorkflow"
      @validate="validateWorkflow"
      @execute="executeWorkflow"
      @fit-view="fitCanvasView"
      @auto-layout="applyAutoLayout"
      @create-node="createNode"
      @import-json="importDefinition"
      @export-json="exportDefinition"
    />

    <div class="editor-main">
      <section class="canvas-panel">
        <div class="meta-form">
          <el-input v-model="meta.name" placeholder="工作流名称" />
          <el-input v-model="meta.workflow_id" placeholder="工作流ID（保存后锁定）" :disabled="Boolean(persistedWorkflowId)" />
          <el-input v-model="meta.description" placeholder="工作流描述" />
          <el-tag>版本 v{{ meta.version }}</el-tag>
        </div>

        <VueFlow
          :id="flowId"
          v-model:nodes="nodes"
          v-model:edges="edges"
          class="workflow-canvas"
          :node-types="nodeTypes"
          :edge-types="edgeTypes"
          :min-zoom="0.2"
          :max-zoom="2.5"
          fit-view-on-init
          @connect="onConnect"
          @node-click="onNodeClick"
          @pane-click="clearSelection"
          @edge-double-click="onEdgeDoubleClick"
        >
          <Background :gap="16" pattern-color="#d2dae8" />
          <Controls position="top-right" />
        </VueFlow>
      </section>

      <aside class="side-panels">
        <NodePropertiesPanel
          :selected-node="selectedNode"
          :node-type-options="availableNodeTypes"
          @update-node="onUpdateNode"
          @delete-node="deleteNode"
          @clone-node="cloneNode"
        />

        <WorkflowTemplateLibrary @apply-template="applyTemplate" @instantiated="openInstantiatedWorkflow" />

        <WorkflowExecutionMonitor
          v-if="persistedWorkflowId"
          :workflow-id="persistedWorkflowId"
          :initial-run-id="activeRunId"
        />
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import {
  addEdge,
  MarkerType,
  Position,
  useVueFlow,
  VueFlow,
  type Connection,
  type Edge,
  type EdgeMouseEvent,
  type Node,
  type NodeMouseEvent
} from '@vue-flow/core';
import { Background } from '@vue-flow/background';
import { Controls } from '@vue-flow/controls';
import '@vue-flow/core/dist/style.css';
import '@vue-flow/core/dist/theme-default.css';
import '@vue-flow/controls/dist/style.css';
import WorkflowNode from './WorkflowNode.vue';
import WorkflowEdge from './WorkflowEdge.vue';
import WorkflowToolbar from './WorkflowToolbar.vue';
import NodePropertiesPanel from './NodePropertiesPanel.vue';
import WorkflowTemplateLibrary from './WorkflowTemplateLibrary.vue';
import WorkflowExecutionMonitor from './WorkflowExecutionMonitor.vue';
import { workflowService } from '../../services/WorkflowService';
import type {
  WorkflowDefinition,
  WorkflowEdgeDefinition,
  WorkflowNodeDefinition,
  WorkflowNodeKind,
  WorkflowRecord,
  WorkflowTemplate
} from '../../types/workflow';
import type { WorkflowCanvasNodeData } from './workflowCanvas';

const route = useRoute();
const router = useRouter();

const flowId = 'workflow-editor-canvas';
const { fitView } = useVueFlow({ id: flowId });

const loading = ref(false);
const nodes = ref<Node<WorkflowCanvasNodeData>[]>([]);
const edges = ref<Edge[]>([]);
const selectedNode = ref<Node<WorkflowCanvasNodeData> | null>(null);
const availableNodeTypes = ref<string[]>([]);
const activeRunId = ref('');
const persistedWorkflowId = ref('');

const meta = reactive({
  workflow_id: '',
  name: '未命名工作流',
  description: '',
  version: 1
});

const nodeTypes = {
  workflowNode: WorkflowNode
};

const edgeTypes = {
  workflowEdge: WorkflowEdge
};

const defaultNodeTypeByKind: Record<WorkflowNodeKind, string> = {
  input: 'input.constant',
  process: 'process.transform',
  output: 'output.collect',
  control: 'control.condition'
};

const normalizeNodeData = (node: Node<WorkflowCanvasNodeData>): WorkflowCanvasNodeData => {
  const kind = node.data?.kind || 'process';
  return {
    kind,
    nodeType: node.data?.nodeType || defaultNodeTypeByKind[kind],
    label: node.data?.label || node.id,
    description: node.data?.description || '',
    enabled: node.data?.enabled !== false,
    params: node.data?.params || {}
  };
};

const routeWorkflowId = computed(() => {
  const raw = route.params.workflowId;
  if (Array.isArray(raw)) {
    return raw[0] || '';
  }
  return typeof raw === 'string' ? raw : '';
});

const buildStarterDefinition = (): WorkflowDefinition => ({
  workflow_id: `wf_${Math.random().toString(36).slice(2, 10)}`,
  name: '新建工作流',
  description: '请在画布中编辑节点和连线',
  version: 1,
  nodes: [
    {
      node_id: 'input_1',
      kind: 'input',
      node_type: 'input.constant',
      params: { value: [1, 2, 3] }
    },
    {
      node_id: 'process_1',
      kind: 'process',
      node_type: 'process.transform',
      params: { operation: 'sum', source: '{{nodes.input_1}}' }
    },
    {
      node_id: 'output_1',
      kind: 'output',
      node_type: 'output.collect',
      params: { fields: ['input_1', 'process_1'] }
    }
  ],
  edges: [
    { source: 'input_1', target: 'process_1', condition: 'always' },
    { source: 'process_1', target: 'output_1', condition: 'always' }
  ]
});

const hydrateFromDefinition = (definition: WorkflowDefinition, keepPersisted = false) => {
  const layout =
    (definition.metadata?.layout as { positions?: Record<string, { x: number; y: number }> } | undefined)
      ?.positions || {};

  const levelMap = new Map<string, number>();
  (definition.dag_levels || []).forEach((group, level) => {
    group.forEach((nodeId) => {
      levelMap.set(nodeId, level);
    });
  });

  const levelCounters = new Map<number, number>();

  nodes.value = definition.nodes.map((node) => {
    const nodeLevel = levelMap.get(node.node_id) ?? 0;
    const levelIndex = levelCounters.get(nodeLevel) ?? 0;
    levelCounters.set(nodeLevel, levelIndex + 1);

    const fallbackPosition = {
      x: 80 + nodeLevel * 260,
      y: 70 + levelIndex * 140
    };

    return {
      id: node.node_id,
      type: 'workflowNode',
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
      position: layout[node.node_id] || fallbackPosition,
      data: {
        kind: node.kind,
        nodeType: node.node_type,
        label: node.name || node.node_id,
        description: node.description || '',
        enabled: node.enabled !== false,
        params: node.params || {}
      }
    };
  });

  edges.value = definition.edges.map((edge) => ({
    id: `${edge.source}_${edge.target}_${Math.random().toString(36).slice(2, 6)}`,
    type: 'workflowEdge',
    source: edge.source,
    target: edge.target,
    markerEnd: MarkerType.ArrowClosed,
    data: {
      condition: edge.condition || 'always'
    }
  }));

  meta.workflow_id = definition.workflow_id;
  meta.name = definition.name;
  meta.description = definition.description || '';
  meta.version = definition.version;

  if (!keepPersisted) {
    persistedWorkflowId.value = '';
  }

  selectedNode.value = null;
  activeRunId.value = '';

  setTimeout(() => {
    fitCanvasView();
  }, 0);
};

const buildDefinitionFromCanvas = (): WorkflowDefinition => {
  const workflowId = meta.workflow_id.trim() || `wf_${Math.random().toString(36).slice(2, 10)}`;

  const nodeDefinitions: WorkflowNodeDefinition[] = nodes.value.map((node) => {
    const data = normalizeNodeData(node);
    return {
      node_id: node.id,
      kind: data.kind,
      node_type: data.nodeType,
      name: data.label,
      description: data.description,
      enabled: data.enabled,
      params: data.params || {}
    };
  });

  const edgeDefinitions: WorkflowEdgeDefinition[] = edges.value.map((edge) => ({
    source: edge.source,
    target: edge.target,
    condition:
      typeof edge.data?.condition === 'string' && edge.data.condition.trim()
        ? edge.data.condition.trim()
        : 'always'
  }));

  const positions = nodes.value.reduce<Record<string, { x: number; y: number }>>((acc, node) => {
    acc[node.id] = { x: node.position.x, y: node.position.y };
    return acc;
  }, {});

  return {
    workflow_id: workflowId,
    name: meta.name.trim() || '未命名工作流',
    description: meta.description.trim(),
    version: meta.version || 1,
    nodes: nodeDefinitions,
    edges: edgeDefinitions,
    metadata: {
      layout: {
        positions
      }
    }
  };
};

const loadWorkflow = async (workflowId: string) => {
  loading.value = true;
  try {
    const detail = await workflowService.getWorkflow(workflowId);
    hydrateFromDefinition(detail.current, true);
    persistedWorkflowId.value = detail.workflow_id;
  } catch {
    ElMessage.error('加载工作流失败');
  } finally {
    loading.value = false;
  }
};

const initNewWorkflow = () => {
  const starter = buildStarterDefinition();
  hydrateFromDefinition(starter, false);
};

const ensureNodeTypeCatalog = async () => {
  try {
    const catalog = await workflowService.listNodeTypes();
    availableNodeTypes.value = [...catalog.built_in, ...catalog.custom];
  } catch {
    availableNodeTypes.value = Object.values(defaultNodeTypeByKind);
  }
};

const onConnect = (connection: Connection) => {
  if (!connection.source || !connection.target) {
    return;
  }

  edges.value = addEdge(
    {
      ...connection,
      id: `edge_${connection.source}_${connection.target}_${Math.random().toString(36).slice(2, 6)}`,
      type: 'workflowEdge',
      markerEnd: MarkerType.ArrowClosed,
      data: {
        condition: 'always'
      }
    },
    edges.value
  ) as Edge[];
};

const onNodeClick = (payload: NodeMouseEvent) => {
  selectedNode.value = payload.node as Node<WorkflowCanvasNodeData>;
};

const clearSelection = () => {
  selectedNode.value = null;
};

const onEdgeDoubleClick = async (payload: EdgeMouseEvent) => {
  const current = typeof payload.edge.data?.condition === 'string' ? payload.edge.data.condition : 'always';
  try {
    const { value } = await ElMessageBox.prompt('请输入连线条件（always 表示始终执行）', '编辑连线条件', {
      inputValue: current,
      confirmButtonText: '保存',
      cancelButtonText: '取消'
    });

    edges.value = edges.value.map((edge) =>
      edge.id === payload.edge.id
        ? {
            ...edge,
            data: {
              ...(edge.data || {}),
              condition: value || 'always'
            }
          }
        : edge
    );
  } catch {
    // 用户取消
  }
};

const createNode = (kind: WorkflowNodeKind) => {
  const id = `${kind}_${Math.random().toString(36).slice(2, 8)}`;
  nodes.value = [
    ...nodes.value,
    {
      id,
      type: 'workflowNode',
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
      position: {
        x: 120 + Math.round(Math.random() * 220),
        y: 80 + Math.round(Math.random() * 220)
      },
      data: {
        kind,
        nodeType: defaultNodeTypeByKind[kind],
        label: id,
        description: '',
        enabled: true,
        params: {}
      }
    }
  ];
};

const onUpdateNode = (payload: { id: string; data: WorkflowCanvasNodeData }) => {
  nodes.value = nodes.value.map((node) => (node.id === payload.id ? { ...node, data: payload.data } : node));
  selectedNode.value = nodes.value.find((item) => item.id === payload.id) || null;
};

const deleteNode = (nodeId: string) => {
  nodes.value = nodes.value.filter((node) => node.id !== nodeId);
  edges.value = edges.value.filter((edge) => edge.source !== nodeId && edge.target !== nodeId);
  selectedNode.value = null;
};

const cloneNode = (nodeId: string) => {
  const source = nodes.value.find((node) => node.id === nodeId);
  if (!source) {
    return;
  }

  const newId = `${source.id}_copy_${Math.random().toString(36).slice(2, 6)}`;
  const sourceData = normalizeNodeData(source);
  nodes.value = [
    ...nodes.value,
    {
      ...source,
      id: newId,
      position: {
        x: source.position.x + 40,
        y: source.position.y + 40
      },
      data: {
        ...sourceData,
        label: `${sourceData.label}_复制`
      }
    }
  ];
};

const fitCanvasView = () => {
  fitView({ duration: 280, padding: 0.2 });
};

const applyAutoLayout = () => {
  const kindOrder: WorkflowNodeKind[] = ['input', 'process', 'control', 'output'];
  const grouped = new Map<WorkflowNodeKind, Node<WorkflowCanvasNodeData>[]>();

  kindOrder.forEach((kind) => grouped.set(kind, []));
  nodes.value.forEach((node) => {
    grouped.get(normalizeNodeData(node).kind)?.push(node);
  });

  nodes.value = kindOrder.flatMap((kind, kindIndex) => {
    const list = grouped.get(kind) || [];
    return list.map((node, nodeIndex) => ({
      ...node,
      position: {
        x: 90 + kindIndex * 260,
        y: 70 + nodeIndex * 140
      }
    }));
  });

  fitCanvasView();
};

const validateWorkflow = async () => {
  loading.value = true;
  try {
    const definition = buildDefinitionFromCanvas();
    const result = await workflowService.validateDefinition(definition);
    ElMessage.success(`校验通过：${result.node_count} 个节点，${result.edge_count} 条连线`);
  } catch {
    ElMessage.error('工作流校验失败，请检查节点参数和连线');
  } finally {
    loading.value = false;
  }
};

const saveWorkflow = async () => {
  loading.value = true;
  try {
    const definition = buildDefinitionFromCanvas();
    await workflowService.validateDefinition(definition);

    let record: WorkflowRecord;
    if (persistedWorkflowId.value) {
      record = await workflowService.updateWorkflow(persistedWorkflowId.value, definition, 'editor_save');
    } else {
      record = await workflowService.createWorkflow(definition);
    }

    persistedWorkflowId.value = record.workflow_id;
    meta.workflow_id = record.workflow_id;
    meta.name = record.name;
    meta.description = record.description;
    meta.version = record.current.version;

    if (routeWorkflowId.value !== record.workflow_id) {
      await router.replace(`/workflows/editor/${record.workflow_id}`);
    }

    ElMessage.success('工作流已保存');
  } catch {
    ElMessage.error('保存失败，请先完成校验错误修复');
  } finally {
    loading.value = false;
  }
};

const executeWorkflow = async () => {
  if (!persistedWorkflowId.value) {
    await saveWorkflow();
    if (!persistedWorkflowId.value) {
      return;
    }
  }

  loading.value = true;
  try {
    const run = await workflowService.executeWorkflow(persistedWorkflowId.value, {
      async: true,
      debug: true,
      trigger: 'admin_console'
    });
    activeRunId.value = run.run_id;
    ElMessage.success(`已触发执行：${run.run_id}`);
  } catch {
    ElMessage.error('触发执行失败');
  } finally {
    loading.value = false;
  }
};

const importDefinition = async (definition: WorkflowDefinition) => {
  try {
    await workflowService.validateDefinition(definition);
    const imported: WorkflowDefinition = {
      ...definition,
      workflow_id: definition.workflow_id || `wf_${Math.random().toString(36).slice(2, 10)}`,
      name: definition.name || '导入工作流',
      version: Number(definition.version || 1)
    };
    hydrateFromDefinition(imported, false);
    ElMessage.success('工作流已导入到画布');
  } catch {
    ElMessage.error('导入的工作流定义无效');
  }
};

const exportDefinition = () => {
  const definition = buildDefinitionFromCanvas();
  const blob = new Blob([JSON.stringify(definition, null, 2)], { type: 'application/json;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${definition.name || definition.workflow_id}.json`;
  link.click();
  URL.revokeObjectURL(url);
  ElMessage.success('工作流JSON已导出');
};

const applyTemplate = (template: WorkflowTemplate) => {
  const nextDefinition: WorkflowDefinition = {
    ...template.workflow,
    workflow_id: `wf_${Math.random().toString(36).slice(2, 10)}`,
    name: `${template.name}_编辑副本`,
    version: 1
  };
  hydrateFromDefinition(nextDefinition, false);
  ElMessage.success(`已加载模板：${template.name}`);
};

const openInstantiatedWorkflow = async (workflowId: string) => {
  if (!workflowId) {
    return;
  }
  await router.push(`/workflows/editor/${workflowId}`);
};

const handleKeyboardShortcuts = (event: KeyboardEvent) => {
  const isMetaOrCtrl = event.metaKey || event.ctrlKey;
  if (isMetaOrCtrl && event.key.toLowerCase() === 's') {
    event.preventDefault();
    void saveWorkflow();
    return;
  }

  if (isMetaOrCtrl && event.key === 'Enter') {
    event.preventDefault();
    void executeWorkflow();
    return;
  }

  if (event.key === 'Delete' && selectedNode.value) {
    event.preventDefault();
    deleteNode(selectedNode.value.id);
  }
};

watch(
  routeWorkflowId,
  (workflowId) => {
    if (workflowId) {
      void loadWorkflow(workflowId);
      return;
    }
    initNewWorkflow();
  },
  { immediate: true }
);

watch(
  nodes,
  () => {
    if (!selectedNode.value) {
      return;
    }
    selectedNode.value = nodes.value.find((node) => node.id === selectedNode.value?.id) || null;
  },
  { deep: true }
);

onMounted(() => {
  void ensureNodeTypeCatalog();
  window.addEventListener('keydown', handleKeyboardShortcuts);
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeyboardShortcuts);
});
</script>

<style scoped>
.workflow-editor-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.editor-main {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 12px;
  min-height: calc(100vh - 220px);
}

.canvas-panel {
  border: 1px solid #d9e2ef;
  border-radius: 12px;
  overflow: hidden;
  background: #fff;
  display: flex;
  flex-direction: column;
}

.meta-form {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1fr) auto;
  gap: 8px;
  padding: 12px;
  border-bottom: 1px solid #e2e8f0;
}

.workflow-canvas {
  flex: 1;
  min-height: 560px;
  background: radial-gradient(circle at 15% 10%, #f7fbff 0%, #f8f9ff 42%, #f4f6fb 100%);
}

.side-panels {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

@media (max-width: 1280px) {
  .editor-main {
    grid-template-columns: 1fr;
  }

  .meta-form {
    grid-template-columns: 1fr;
  }

  .workflow-canvas {
    min-height: 500px;
  }
}
</style>
