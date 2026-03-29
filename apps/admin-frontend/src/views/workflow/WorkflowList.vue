<template>
  <div class="workflow-list-page">
    <section class="stats-grid">
      <el-card>
        <template #header>工作流总数</template>
        <div class="stat-value">{{ workflows.length }}</div>
      </el-card>
      <el-card>
        <template #header>累计运行次数</template>
        <div class="stat-value">{{ metrics.total_runs }}</div>
      </el-card>
      <el-card>
        <template #header>执行成功率</template>
        <div class="stat-value">{{ successRateText }}</div>
      </el-card>
      <el-card>
        <template #header>平均耗时</template>
        <div class="stat-value">{{ metrics.avg_duration_ms.toFixed(0) }} ms</div>
      </el-card>
    </section>

    <section class="page-card">
      <div class="toolbar">
        <el-input v-model="filters.keyword" placeholder="搜索名称/ID/描述" clearable style="width: 260px" />
        <el-input-number v-model="filters.minVersion" :min="1" :max="999" controls-position="right" />
        <el-button type="primary" @click="loadData">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
        <el-button type="success" @click="goEditor()">新建工作流</el-button>
      </div>

      <el-table :data="filteredWorkflows" border>
        <el-table-column prop="workflow_id" label="工作流ID" min-width="180" />
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column prop="description" label="描述" min-width="200" />
        <el-table-column prop="version" label="版本" width="80" />
        <el-table-column prop="collaborator_count" label="协作者" width="90" />
        <el-table-column prop="updated_at" label="更新时间" min-width="180" />
        <el-table-column label="操作" width="350" fixed="right">
          <template #default="scope">
            <el-button size="small" @click="goEditor(scope.row.workflow_id)">编辑</el-button>
            <el-button size="small" @click="openShareDialog(scope.row.workflow_id)">分享</el-button>
            <el-button size="small" @click="cloneByExport(scope.row.workflow_id)">复制</el-button>
            <el-button size="small" type="danger" @click="onDelete(scope.row.workflow_id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="shareDialogVisible" title="工作流协作分享" width="620px">
      <div class="share-toolbar">
        <el-button size="small" @click="appendCollaborator">添加协作者</el-button>
      </div>

      <div class="share-list">
        <div v-for="(item, index) in collaborators" :key="`col_${index}`" class="share-row">
          <el-input v-model="item.user_id" placeholder="用户ID" />
          <el-select v-model="item.role" style="width: 130px">
            <el-option label="owner" value="owner" />
            <el-option label="editor" value="editor" />
            <el-option label="viewer" value="viewer" />
          </el-select>
          <el-input v-model="item.display_name" placeholder="显示名称（可选）" />
          <el-button type="danger" plain @click="removeCollaborator(index)">移除</el-button>
        </div>
      </div>

      <template #footer>
        <el-button @click="shareDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveCollaborators">保存</el-button>
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

const router = useRouter();
const loading = ref(false);
const workflows = ref<WorkflowListItem[]>([]);
const metrics = reactive<WorkflowMetrics>({
  total_runs: 0,
  success_runs: 0,
  failed_runs: 0,
  avg_duration_ms: 0,
  last_updated_at: ''
});

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
    ElMessage.error('加载工作流列表失败');
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
    await ElMessageBox.confirm('删除后不可恢复，是否继续？', '删除工作流', {
      type: 'warning'
    });
    await workflowService.deleteWorkflow(workflowId);
    ElMessage.success('已删除工作流');
    await loadData();
  } catch {
    // 用户取消或请求失败
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
    ElMessage.error('加载协作者失败');
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
    ElMessage.success('协作者设置已保存');
    shareDialogVisible.value = false;
    await loadData();
  } catch {
    ElMessage.error('保存协作者失败');
  }
};

const cloneByExport = async (workflowId: string) => {
  try {
    const definition = await workflowService.exportWorkflow(workflowId);
    definition.workflow_id = `wf_${Math.random().toString(36).slice(2, 10)}`;
    definition.name = `${definition.name}_复制`;
    definition.version = 1;
    await workflowService.createWorkflow(definition);
    ElMessage.success('已复制工作流');
    await loadData();
  } catch {
    ElMessage.error('复制工作流失败');
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
