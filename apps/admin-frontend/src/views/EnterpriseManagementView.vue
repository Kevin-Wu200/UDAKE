<template>
  <div class="enterprise-management-page">
    <section class="overview-grid">
      <el-card>
        <template #header>{{ tc('companymenbernum') }}</template>
        <div class="value">{{ members.length }}</div>
      </el-card>
      <el-card>
        <template #header>{{ tc('workflowtotalnum') }}</template>
        <div class="value">{{ resource.totalTasks }}</div>
      </el-card>
      <el-card>
        <template #header>{{ tc('transmittingmission') }}</template>
        <div class="value">{{ resource.transferringTasks }}</div>
      </el-card>
    </section>

    <section class="panel-grid">
      <el-card>
        <template #header>{{ tc('menbermanage') }}</template>
        <el-table :data="members" border>
          <el-table-column prop="user_id" :label="tc('userid')" width="160" />
          <el-table-column prop="display_name" :label="tc('name')" min-width="140" />
          <el-table-column prop="role" :label="tc('rights')" width="140">
            <template #default="scope">
              <el-select v-model="scope.row.role" @change="onRoleChange(scope.row)">
                <el-option :label="tc('menber')" value="member" />
                <el-option :label="tc('manager')" value="manager" />
              </el-select>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card>
        <template #header>{{ tc('sourceband') }}</template>
        <el-descriptions :column="1" border>
          <el-descriptions-item :label="tc('processhold')">{{ resource.pendingTasks }}</el-descriptions-item>
          <el-descriptions-item :label="tc('processing')">{{ resource.runningTasks }}</el-descriptions-item>
          <el-descriptions-item :label="tc('processdone')">{{ resource.completedTasks }}</el-descriptions-item>
          <el-descriptions-item :label="tc('processfailed')">{{ resource.failedTasks }}</el-descriptions-item>
        </el-descriptions>
      </el-card>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { workflowService } from '../services/WorkflowService';
import { useI18nText } from '../i18n/useI18n';

const { tc } = useI18nText();

type EnterpriseMember = {
  user_id: string;
  display_name: string;
  role: 'member' | 'manager';
};

const members = ref<EnterpriseMember[]>([]);
const resource = reactive({
  totalTasks: 0,
  transferringTasks: 0,
  pendingTasks: 0,
  runningTasks: 0,
  completedTasks: 0,
  failedTasks: 0
});

const loadData = async () => {
  try {
    const { workflows } = await workflowService.listWorkflows();
    const memberMap = new Map<string, EnterpriseMember>();
    let totalTasks = 0;
    let transferringTasks = 0;
    let pendingTasks = 0;
    let runningTasks = 0;
    let completedTasks = 0;
    let failedTasks = 0;

    for (const wf of workflows) {
      const detail = await workflowService.getWorkflow(wf.workflow_id);
      (detail.collaborators || []).forEach((c) => {
        if (!c.user_id) return;
        if (!memberMap.has(c.user_id)) {
          memberMap.set(c.user_id, {
            user_id: c.user_id,
            display_name: c.display_name || c.user_id,
            role: c.role === 'admin' ? 'manager' : 'member'
          });
        }
      });

      const taskList = await workflowService.listWorkflowTasks(wf.workflow_id);
      for (const task of taskList.tasks || []) {
        totalTasks += 1;
        const status = String(task.status || 'pending');
        if (status === 'transferring') transferringTasks += 1;
        if (status === 'pending') pendingTasks += 1;
        if (status === 'running') runningTasks += 1;
        if (status === 'completed') completedTasks += 1;
        if (status === 'failed') failedTasks += 1;
      }
    }

    members.value = Array.from(memberMap.values());
    resource.totalTasks = totalTasks;
    resource.transferringTasks = transferringTasks;
    resource.pendingTasks = pendingTasks;
    resource.runningTasks = runningTasks;
    resource.completedTasks = completedTasks;
    resource.failedTasks = failedTasks;
  } catch (e) {
    ElMessage.error(tc('companydataloadfailed'));
  }
};

const onRoleChange = async (member: EnterpriseMember) => {
  try {
    const { workflows } = await workflowService.listWorkflows();
    for (const wf of workflows) {
      const detail = await workflowService.getWorkflow(wf.workflow_id);
      const collaborators = (detail.collaborators || []).map((item) => {
        if (item.user_id === member.user_id) {
          return {
            ...item,
            role: member.role === 'manager' ? 'admin' : 'viewer'
          };
        }
        return item;
      });
      await workflowService.updateCollaborators(wf.workflow_id, collaborators);
    }
    ElMessage.success(tc('rightschangedsuccess'));
  } catch {
    ElMessage.error(tc('rightschangedfailed'));
  }
};

onMounted(() => {
  void loadData();
});
</script>

<style scoped>
.enterprise-management-page { display: flex; flex-direction: column; gap: 12px; }
.overview-grid { display: grid; gap: 12px; grid-template-columns: repeat(3, minmax(0, 1fr)); }
.panel-grid { display: grid; gap: 12px; grid-template-columns: repeat(2, minmax(0, 1fr)); }
.value { font-size: 28px; font-weight: 700; }
@media (max-width: 960px) {
  .overview-grid, .panel-grid { grid-template-columns: 1fr; }
}
</style>
