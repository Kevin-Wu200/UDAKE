<template>
  <div class="toolbar-wrap">
    <div class="left-actions">
      <el-button type="primary" :loading="loading" @click="emit('save')">{{ t('save') }}</el-button>
      <el-button :loading="loading" @click="emit('validate')">{{ t ('calibrate') }}</el-button>
      <el-button type="success" :loading="loading" :disabled="!canExecute" @click="emit('execute')">
        {{ t('exec') }}
      </el-button>
      <el-button @click="emit('fit-view')">{{ t('adaptcanva') }}</el-button>
      <el-button @click="emit('auto-layout')">{{ t('automaticlayout') }}</el-button>
    </div>

    <div class="right-actions">
      <el-dropdown @command="handleCreateNode">
        <el-button>
          {{ t('addnodes') }}
          <el-icon class="el-icon--right"><ArrowDown /></el-icon>
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="input">{{ t('inputnode') }}</el-dropdown-item>
            <el-dropdown-item command="process">{{ t('accessnode') }}</el-dropdown-item>
            <el-dropdown-item command="output">{{ t('outputnode') }}</el-dropdown-item>
            <el-dropdown-item command="control">{{ t('controlnode') }}</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>

      <el-button @click="triggerImport">{{ t('import') }}</el-button>
      <el-button :disabled="!hasWorkflow" @click="emit('export-json')">{{ t('derive') }}</el-button>
      <input ref="fileInputRef" type="file" accept="application/json" class="file-input" @change="onFileChange" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { ArrowDown } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import type { WorkflowDefinition, WorkflowNodeKind } from '../../types/workflow';
import { useI18nText } from '../../i18n/useI18n';

const { t } = useI18nText();

withDefaults(
  defineProps<{
    loading?: boolean;
    hasWorkflow?: boolean;
    canExecute?: boolean;
  }>(),
  {
    loading: false,
    hasWorkflow: false,
    canExecute: false
  }
);

const emit = defineEmits<{
  save: [];
  validate: [];
  execute: [];
  'fit-view': [];
  'auto-layout': [];
  'create-node': [kind: WorkflowNodeKind];
  'import-json': [definition: WorkflowDefinition];
  'export-json': [];
}>();

const fileInputRef = ref<HTMLInputElement | null>(null);

const handleCreateNode = (kind: string) => {
  if (kind === 'input' || kind === 'process' || kind === 'output' || kind === 'control') {
    emit('create-node', kind);
  }
};

const triggerImport = () => {
  fileInputRef.value?.click();
};

const onFileChange = async (event: Event) => {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0];
  if (!file) {
    return;
  }

  try {
    const text = await file.text();
    const json = JSON.parse(text) as WorkflowDefinition;
    emit('import-json', json);
  } catch {
    ElMessage.error( t('importworkflowjsonfailed') );
  } finally {
    target.value = '';
  }
};
</script>

<style scoped>
.toolbar-wrap {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 10px 12px;
  border: 1px solid #d9e2ef;
  border-radius: 10px;
  background: #ffffff;
}

.left-actions,
.right-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.file-input {
  display: none;
}
</style>
