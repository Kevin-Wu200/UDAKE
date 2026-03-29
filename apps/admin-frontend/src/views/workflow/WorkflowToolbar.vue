<template>
  <div class="toolbar-wrap">
    <div class="left-actions">
      <el-button type="primary" :loading="loading" @click="emit('save')">保存</el-button>
      <el-button :loading="loading" @click="emit('validate')">校验</el-button>
      <el-button type="success" :loading="loading" :disabled="!canExecute" @click="emit('execute')">
        执行
      </el-button>
      <el-button @click="emit('fit-view')">适配画布</el-button>
      <el-button @click="emit('auto-layout')">自动布局</el-button>
    </div>

    <div class="right-actions">
      <el-dropdown @command="handleCreateNode">
        <el-button>
          添加节点
          <el-icon class="el-icon--right"><ArrowDown /></el-icon>
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="input">输入节点</el-dropdown-item>
            <el-dropdown-item command="process">处理节点</el-dropdown-item>
            <el-dropdown-item command="output">输出节点</el-dropdown-item>
            <el-dropdown-item command="control">控制节点</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>

      <el-button @click="triggerImport">导入</el-button>
      <el-button :disabled="!hasWorkflow" @click="emit('export-json')">导出</el-button>
      <input ref="fileInputRef" type="file" accept="application/json" class="file-input" @change="onFileChange" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { ArrowDown } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import type { WorkflowDefinition, WorkflowNodeKind } from '../../types/workflow';

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
    ElMessage.error('导入失败：不是合法的工作流 JSON 文件');
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
