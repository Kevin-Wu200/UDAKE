<template>
  <div class="panel-card">
    <div class="panel-title">{{ t('nodeattribute') }}</div>

    <template v-if="selectedNode">
      <el-form label-position="top" class="prop-form">
        <el-form-item :label="t('nodeid')">
          <el-input :model-value="selectedNode.id" disabled />
        </el-form-item>

        <el-form-item :label="t('nodename')">
          <el-input v-model="form.label" @change="emitNodeUpdate" />
        </el-form-item>

        <el-form-item :label="t('nodetype')">
          <el-select v-model="form.kind" style="width: 100%" @change="emitNodeUpdate">
            <el-option :label="t('input')" value="input" />
            <el-option :label="t('access')" value="process" />
            <el-option :label="t('output')" value="output" />
            <el-option :label="t('control')" value="control" />
          </el-select>
        </el-form-item>

        <el-form-item :label="t('processor')">
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

        <el-form-item :label="t('enablestatus')">
          <el-switch v-model="form.enabled" @change="emitNodeUpdate" />
        </el-form-item>

        <el-form-item :label="t('nodedescription')">
          <el-input v-model="form.description" type="textarea" :rows="2" @change="emitNodeUpdate" />
        </el-form-item>

        <el-form-item :label="t('jsonparameter')">
          <el-input
            v-model="form.paramsText"
            type="textarea"
            :rows="8"
            placeholder="${t('illegaljsonwarning')} {&quot;step&quot;: 2}"
          />
        </el-form-item>

        <el-button type="primary" @click="applyParams">{{ t('applyparameter') }}</el-button>
      </el-form>

      <div class="panel-actions">
        <el-button type="warning" plain @click="emit('clone-node', selectedNode.id)">{{ t('copynode') }}</el-button>
        <el-button type="danger" plain @click="emit('delete-node', selectedNode.id)">{{ t('deletenode') }}</el-button>
      </div>
    </template>

    <el-empty v-else :description="t('nodeselectRequired')" :image-size="70" />
  </div>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue';
import { ElMessage } from 'element-plus';
import type { Node } from '@vue-flow/core';
import type { WorkflowCanvasNodeData } from './workflowCanvas';
import { useI18nText } from '../../i18n/useI18n';

const { t } = useI18nText();

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
    ElMessage.success(t('nodeparameterrefreshsuccess'));
  } catch {
    ElMessage.error(t('nodeparameterjsoninvalid'));
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
