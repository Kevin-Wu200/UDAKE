<template>
  <div class="panel-card">
    <div class="panel-title">节点属性</div>

    <template v-if="selectedNode">
      <el-form label-position="top" class="prop-form">
        <el-form-item label="节点ID">
          <el-input :model-value="selectedNode.id" disabled />
        </el-form-item>

        <el-form-item label="节点名称">
          <el-input v-model="form.label" @change="emitNodeUpdate" />
        </el-form-item>

        <el-form-item label="节点类型">
          <el-select v-model="form.kind" style="width: 100%" @change="emitNodeUpdate">
            <el-option label="输入" value="input" />
            <el-option label="处理" value="process" />
            <el-option label="输出" value="output" />
            <el-option label="控制" value="control" />
          </el-select>
        </el-form-item>

        <el-form-item label="处理器">
          <el-select
            v-if="nodeTypeOptions.length"
            v-model="form.nodeType"
            filterable
            allow-create
            default-first-option
            style="width: 100%"
            @change="emitNodeUpdate"
          >
            <el-option v-for="item in nodeTypeOptions" :key="item" :label="item" :value="item" />
          </el-select>
          <el-input v-else v-model="form.nodeType" @change="emitNodeUpdate" />
        </el-form-item>

        <el-form-item label="启用状态">
          <el-switch v-model="form.enabled" @change="emitNodeUpdate" />
        </el-form-item>

        <el-form-item label="节点描述">
          <el-input v-model="form.description" type="textarea" :rows="2" @change="emitNodeUpdate" />
        </el-form-item>

        <el-form-item label="参数(JSON)">
          <el-input
            v-model="form.paramsText"
            type="textarea"
            :rows="8"
            placeholder="请输入合法 JSON，例如 {&quot;step&quot;: 2}"
          />
        </el-form-item>

        <el-button type="primary" @click="applyParams">应用参数</el-button>
      </el-form>

      <div class="panel-actions">
        <el-button type="warning" plain @click="emit('clone-node', selectedNode.id)">复制节点</el-button>
        <el-button type="danger" plain @click="emit('delete-node', selectedNode.id)">删除节点</el-button>
      </div>
    </template>

    <el-empty v-else description="请在画布中选择一个节点" :image-size="70" />
  </div>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue';
import { ElMessage } from 'element-plus';
import type { Node } from '@vue-flow/core';
import type { WorkflowCanvasNodeData } from './workflowCanvas';

interface PanelForm {
  label: string;
  kind: WorkflowCanvasNodeData['kind'];
  nodeType: string;
  description: string;
  enabled: boolean;
  paramsText: string;
}

const props = withDefaults(
  defineProps<{
    selectedNode: Node<WorkflowCanvasNodeData> | null;
    nodeTypeOptions?: string[];
  }>(),
  {
    nodeTypeOptions: () => []
  }
);

const emit = defineEmits<{
  'update-node': [
    {
      id: string;
      data: WorkflowCanvasNodeData;
    }
  ];
  'delete-node': [nodeId: string];
  'clone-node': [nodeId: string];
}>();

const form = reactive<PanelForm>({
  label: '',
  kind: 'process',
  nodeType: '',
  description: '',
  enabled: true,
  paramsText: '{}'
});

watch(
  () => props.selectedNode,
  (node) => {
    if (!node) {
      return;
    }
    const nodeData = node.data || {
      kind: 'process',
      nodeType: 'process.transform',
      label: node.id,
      description: '',
      enabled: true,
      params: {}
    };
    form.label = nodeData.label;
    form.kind = nodeData.kind;
    form.nodeType = nodeData.nodeType;
    form.description = nodeData.description || '';
    form.enabled = nodeData.enabled;
    form.paramsText = JSON.stringify(nodeData.params || {}, null, 2);
  },
  { immediate: true }
);

const emitNodeUpdate = () => {
  if (!props.selectedNode) {
    return;
  }

  let parsedParams: Record<string, unknown> = {};
  try {
    parsedParams = JSON.parse(form.paramsText);
  } catch {
    parsedParams = props.selectedNode.data?.params || {};
  }

  emit('update-node', {
    id: props.selectedNode.id,
    data: {
      kind: form.kind,
      nodeType: form.nodeType,
      label: form.label || props.selectedNode.id,
      description: form.description,
      enabled: form.enabled,
      params: parsedParams
    }
  });
};

const applyParams = () => {
  if (!props.selectedNode) {
    return;
  }

  try {
    const parsed = JSON.parse(form.paramsText);
    emit('update-node', {
      id: props.selectedNode.id,
      data: {
        ...(props.selectedNode.data || {}),
        kind: form.kind,
        nodeType: form.nodeType,
        label: form.label || props.selectedNode.id,
        description: form.description,
        enabled: form.enabled,
        params: parsed
      }
    });
    ElMessage.success('节点参数已更新');
  } catch {
    ElMessage.error('参数 JSON 格式无效');
  }
};
</script>

<style scoped>
.panel-card {
  border: 1px solid #d9e2ef;
  border-radius: 10px;
  background: #fff;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.panel-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.prop-form {
  display: flex;
  flex-direction: column;
}

.panel-actions {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}
</style>
