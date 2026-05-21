<template>
  <div class="workflow-list-page">
    <section class="stats-grid">
      <el-card>
        <template #header>{{ t('totalWorkflows') }}</template>
        <div class="stat-value">{{ workflows.length }}</div>
      </el-card>
      <el-card>
        <template #header>{{ t('totalRuns') }}</template>
        <div class="stat-value">{{ metrics.total_runs }}</div>
      </el-card>
      <el-card>
        <template #header>{{ t('successRate') }}</template>
        <div class="stat-value">{{ successRateText }}</div>
      </el-card>
      <el-card>
        <template #header>{{ t('avgDuration') }}</template>
        <div class="stat-value">{{ metrics.avg_duration_ms.toFixed(0) }} ms</div>
      </el-card>
    </section>

    <section class="page-card">
      <div class="toolbar">
        <el-input v-model="filters.keyword" :placeholder="t('searchNameIdDescription')" clearable style="width: 260px" />
        <el-input-number v-model="filters.minVersion" :min="1" :max="999" controls-position="right" />
        <el-button type="primary" @click="loadData">{{ t('search') }}</el-button>
        <el-button @click="resetFilters">{{ t('reset') }}</el-button>
        <el-button type="success" @click="goEditor()">{{ t('createWorkflow') }}</el-button>
        <div class="quick-entry">
          <el-input
            v-model="quickWorkflowId"
            placeholder="ID 进入工作流..."
            size="default"
            style="width: 200px"
            clearable
            @keyup.enter="goEditor(quickWorkflowId)"
          >
            <template #append>
              <el-button @click="goEditor(quickWorkflowId)">{{ t('go') }}</el-button>
            </template>
          </el-input>
        </div>
      </div>

      <el-table :data="filteredWorkflows" border>
        <el-table-column prop="workflow_id" :label="t('workflowID')" min-width="180" />
        <el-table-column prop="name" :label="t('workflowName')" min-width="160" />
        <el-table-column prop="description" :label="t('description')" min-width="200" />
        <el-table-column prop="version" :label="t('version')" width="80" />
        <el-table-column prop="collaborator_count" :label="t('coworkers')" width="90" />
        <el-table-column prop="updated_at" :label="t('updatetime')" min-width="180" />
        <el-table-column :label="t('actions')" width="350" fixed="right">
          <template #default="scope">
            <el-button size="small" @click="goEditor(scope.row.workflow_id)">{{ t('edit') }}</el-button>
            <el-button size="small" @click="openShareDialog(scope.row.workflow_id)">{{ t('share') }}</el-button>
            <el-button size="small" @click="cloneByExport(scope.row.workflow_id)">{{ t('copy') }}</el-button>
            <el-button size="small" type="danger" @click="onDelete(scope.row.workflow_id)">{{ t('delete') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="shareDialogVisible" :title="t('workflowSharecowork')" width="620px">
      <div class="share-toolbar">
        <el-button size="small" @click="appendCollaborator">{{ t('addcoworker') }}</el-button>
      </div>

      <div class="share-list">
        <div v-for="(item, index) in collaborators" :key="`col_${index}`" class="share-row">
          <el-input v-model="item.user_id" :placeholder="t('userid')" />
          <el-select v-model="item.role" style="width: 130px">
            <el-option :label="t('owner')" value="owner" />
            <el-option :label="t('editor')" value="editor" />
            <el-option :label="t('viewer')" value="viewer" />
          </el-select>
          <el-input v-model="item.display_name" :placeholder="t('displayname')" />
          <el-button type="danger" plain @click="removeCollaborator(index)">{{ t('remove') }}</el-button>
        </div>
      </div>

      <template #footer>
        <el-button @click="shareDialogVisible = false">{{ t('cancel') }}</el-button>
        <el-button type="primary" @click="saveCollaborators">{{ t('save') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import { workflowService } from '../../services/WorkflowService';
import type { WorkflowCollaborator, WorkflowListItem, WorkflowMetrics } from '../../types/workflow';
import { useI18nText } from '../../i18n/useI18n';

const router = useRouter();
const loading = ref(false);
const quickWorkflowId = ref('');
const workflows = ref<WorkflowListItem[]>([]);
const metrics = reactive<WorkflowMetrics>({
  total_runs: 0,
  success_runs: 0,
  failed_runs: 0,
  avg_duration_ms: 0,
  last_updated_at: ''
});
const { t } = useI18nText();

const filters = reactive({
  keyword: '',
  minVersion: 1
});

const shareDialogVisible = ref(false);
const currentShareWorkflowId = ref('');
const collaborators = ref<WorkflowCollaborator[]>([]);

const successRateText = computed(() => {
  const total = metrics.total_runs || 0;
  if (!total) {
    return '0%';
  }
  return `${((metrics.success_runs / total) * 100).toFixed(1)}%`;
});

const filteredWorkflows = computed(() => {
  const query = filters.keyword.trim().toLowerCase();

  return workflows.value.filter((item) => {
    const byVersion = item.version >= Number(filters.minVersion || 1);
    if (!query) {
      return byVersion;
    }
    const text = `${item.workflow_id} ${item.name} ${item.description}`.toLowerCase();
    return byVersion && text.includes(query);
  });
});

const loadData = async () => {
  loading.value = true;
  try {
    const [listRes, perfRes] = await Promise.all([
      workflowService.listWorkflows(),
      workflowService.getPerformanceMetrics()
    ]);

    workflows.value = listRes.workflows.sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1));
    Object.assign(metrics, perfRes);
  } catch {
    ElMessage.error(t('loadworkflowslistfailed'));
  } finally {
    loading.value = false;
  }
};

const resetFilters = () => {
  filters.keyword = '';
  filters.minVersion = 1;
  void loadData();
};

const goEditor = (workflowId?: string) => {
  if (workflowId) {
    router.push(`/workflows/editor/${workflowId}`);
    return;
  }
  router.push('/workflows/editor');
};

const onDelete = async (workflowId: string) => {
  try {
    await ElMessageBox.confirm(t('deletewarning'), t('deleteworkflow'), {
      type: 'warning',
      confirmButtonText: t('delete'),
      cancelButtonText: t('cancel'),
      modalClass: 'admin-confirm-dialog-overlay',
      closeOnClickModal: false,
      closeOnPressEscape: false
    });
    await workflowService.deleteWorkflow(workflowId);
    ElMessage.success(t('workflowdeleted'));
    await loadData();
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      console.error(t('workflowdeletefailed'), error);
      ElMessage.error(t('actionfailed'));
    }
  }
};

const openShareDialog = async (workflowId: string) => {
  currentShareWorkflowId.value = workflowId;
  try {
    const detail = await workflowService.getWorkflow(workflowId);
    collaborators.value = detail.collaborators?.length
      ? detail.collaborators.map((item) => ({ ...item }))
      : [{ user_id: '', role: 'viewer', display_name: '' }];
    shareDialogVisible.value = true;
  } catch {
    ElMessage.error(t('loadcoworkerfailed'));
  }
};

const appendCollaborator = () => {
  collaborators.value.push({ user_id: '', role: 'viewer', display_name: '' });
};

const removeCollaborator = (index: number) => {
  collaborators.value.splice(index, 1);
};

const saveCollaborators = async () => {
  if (!currentShareWorkflowId.value) {
    return;
  }

  const sanitized = collaborators.value.filter((item) => item.user_id.trim()).map((item) => ({
    user_id: item.user_id.trim(),
    role: item.role,
    display_name: item.display_name?.trim() || undefined
  }));

  try {
    await workflowService.updateCollaborators(currentShareWorkflowId.value, sanitized);
    ElMessage.success(t('savecoworkersuccess'));
    shareDialogVisible.value = false;
    await loadData();
  } catch {
    ElMessage.error(t('savecoworkerfailed'));
  }
};

const cloneByExport = async (workflowId: string) => {
  try {
    const definition = await workflowService.exportWorkflow(workflowId);
    definition.workflow_id = `wf_${Math.random().toString(36).slice(2, 10)}`;
    definition.name = `${definition.name}_${t('copy')}`;
    definition.version = 1;
    await workflowService.createWorkflow(definition);
    ElMessage.success(t('workflowcloned'));
    await loadData();
  } catch {
    ElMessage.error(t('workflowclonefailed'));
  }
};

onMounted(() => {
  void loadData();
});
</script>

<style scoped>
.workflow-list-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.stat-value {
  font-size: 26px;
  font-weight: 700;
  color: #0f172a;
}

.share-toolbar {
  margin-bottom: 10px;
}

.share-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.share-row {
  display: grid;
  grid-template-columns: 1.2fr 130px 1fr 80px;
  gap: 8px;
}

.quick-entry {
  margin-left: auto;
}

@media (max-width: 1080px) {
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .share-row {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
