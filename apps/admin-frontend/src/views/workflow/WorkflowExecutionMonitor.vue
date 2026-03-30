<template>
  <div class="panel-card">
    <div class="panel-header">
      <div>
        <div class="panel-title">执行监控</div>
        <div class="panel-subtitle">WebSocket + 轮询双通道实时更新</div>
      </div>
      <div class="header-actions">
        <el-tag :type="wsConnected ? 'success' : 'warning'">{{ wsConnected ? 'WS已连接' : 'WS重连中' }}</el-tag>
        <el-button link type="primary" @click="refresh">刷新</el-button>
      </div>
    </div>

    <div class="summary" v-if="selectedRun">
      <el-progress :percentage="Math.round(selectedRun.progress || 0)" :status="progressStatus" />
      <div class="summary-grid">
        <div>运行ID：{{ selectedRun.run_id }}</div>
        <div>状态：{{ selectedRun.status }}</div>
        <div>触发源：{{ selectedRun.trigger }}</div>
        <div>耗时：{{ formatDuration(selectedRun.duration_ms) }}</div>
      </div>
      <el-alert v-if="selectedRun.error" :title="selectedRun.error" type="error" :closable="false" show-icon />
    </div>

    <el-empty v-else description="暂无执行记录" :image-size="64" />

    <el-table :data="runs" size="small" height="220" @row-click="onSelectRun">
      <el-table-column prop="run_id" label="运行ID" min-width="170" />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="scope">
          <el-tag :type="runStatusTag(scope.row.status)">{{ scope.row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="progress" label="进度" width="100">
        <template #default="scope">{{ Math.round(scope.row.progress || 0) }}%</template>
      </el-table-column>
      <el-table-column prop="started_at" label="开始时间" min-width="180" />
    </el-table>

    <el-scrollbar v-if="logs.length" height="180px" class="logs">
      <div v-for="(log, index) in logs" :key="`${log.ts}_${index}`" class="log-item">
        <span class="ts">{{ log.ts }}</span>
        <span class="event">{{ log.node_id }} · {{ log.event }}</span>
        <span class="msg">{{ log.message }}</span>
      </div>
    </el-scrollbar>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { workflowService } from '../../services/WorkflowService';
import { workflowRealtimeService } from '../../services/WorkflowRealtimeService';
import type { WorkflowRunDetail, WorkflowRunItem, WorkflowRunLog } from '../../types/workflow';

const props = defineProps<{
  workflowId: string;
  initialRunId?: string;
}>();

const runs = ref<WorkflowRunItem[]>([]);
const selectedRun = ref<WorkflowRunDetail | null>(null);
const logs = ref<WorkflowRunLog[]>([]);
const wsConnected = ref(false);

let pollTimer: number | null = null;
let unsubscribeRealtime: (() => void) | null = null;
let pollIntervalMs = 3_000;
let refreshQueued = false;

const progressStatus = computed(() => {
  if (!selectedRun.value) {
    return undefined;
  }
  if (selectedRun.value.status === 'failed') {
    return 'exception';
  }
  if (selectedRun.value.status === 'completed') {
    return 'success';
  }
  return undefined;
});

const runStatusTag = (status: string) => {
  if (status === 'completed') {
    return 'success';
  }
  if (status === 'failed') {
    return 'danger';
  }
  if (status === 'running') {
    return 'warning';
  }
  return 'info';
};

const formatDuration = (durationMs: number | null) => {
  if (!durationMs) {
    return '-';
  }
  return `${durationMs.toFixed(0)} ms`;
};

const refresh = async () => {
  if (!props.workflowId) {
    runs.value = [];
    selectedRun.value = null;
    logs.value = [];
    workflowRealtimeService.setRunSubscription('');
    return;
  }

  const runList = await workflowService.listWorkflowRuns(props.workflowId, 50);
  runs.value = runList.runs;

  const targetRunId = selectedRun.value?.run_id || props.initialRunId || runList.runs[0]?.run_id;
  if (!targetRunId) {
    selectedRun.value = null;
    logs.value = [];
    workflowRealtimeService.setRunSubscription('');
    return;
  }

  await loadRunDetail(targetRunId);
};

const loadRunDetail = async (runId: string) => {
  const detail = await workflowService.getRun(runId);
  selectedRun.value = detail;
  workflowRealtimeService.setRunSubscription(detail.run_id);
  const logResult = await workflowService.getRunLogs(runId);
  logs.value = logResult.logs;
};

const onSelectRun = async (row: WorkflowRunItem) => {
  await loadRunDetail(row.run_id);
};

const startPolling = () => {
  stopPolling();
  pollTimer = window.setInterval(() => {
    void refresh();
  }, pollIntervalMs);
};

const stopPolling = () => {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer);
    pollTimer = null;
  }
};

const restartPolling = (intervalMs: number) => {
  pollIntervalMs = intervalMs;
  startPolling();
};

const queueRefresh = () => {
  if (refreshQueued) {
    return;
  }
  refreshQueued = true;
  window.setTimeout(() => {
    refreshQueued = false;
    void refresh();
  }, 120);
};

watch(
  () => props.workflowId,
  () => {
    workflowRealtimeService.setWorkflowSubscription(props.workflowId);
    workflowRealtimeService.setRunSubscription('');
    void refresh();
  }
);

onMounted(() => {
  workflowRealtimeService.start();
  workflowRealtimeService.setWorkflowSubscription(props.workflowId);
  if (props.initialRunId) {
    workflowRealtimeService.setRunSubscription(props.initialRunId);
  }

  unsubscribeRealtime = workflowRealtimeService.subscribe((event) => {
    if (event.type === 'connected') {
      wsConnected.value = true;
      restartPolling(10_000);
      return;
    }
    if (event.type === 'disconnected' || event.type === 'error') {
      wsConnected.value = false;
      restartPolling(3_000);
      return;
    }

    if (event.type === 'workflow_run_update' || event.type === 'workflow_update') {
      const eventWorkflowId = typeof event.payload.workflow_id === 'string' ? event.payload.workflow_id : '';
      if (!eventWorkflowId || eventWorkflowId === props.workflowId) {
        queueRefresh();
      }
      return;
    }

    queueRefresh();
  });

  void refresh();
  startPolling();
});

onBeforeUnmount(() => {
  stopPolling();
  workflowRealtimeService.setRunSubscription('');
  workflowRealtimeService.setWorkflowSubscription('');
  workflowRealtimeService.stop();
  unsubscribeRealtime?.();
  unsubscribeRealtime = null;
});
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

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.panel-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.panel-subtitle {
  font-size: 12px;
  color: #64748b;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.summary {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
  font-size: 12px;
  color: #334155;
}

.logs {
  border: 1px dashed #d7dee9;
  border-radius: 8px;
  padding: 6px;
}

.log-item {
  display: grid;
  grid-template-columns: 1.3fr 1fr 2fr;
  gap: 8px;
  font-size: 12px;
  padding: 4px 0;
  border-bottom: 1px solid #eef2f7;
}

.log-item:last-child {
  border-bottom: none;
}

.ts {
  color: #475569;
}

.event {
  color: #0f766e;
}

.msg {
  color: #334155;
}

@media (max-width: 960px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .log-item {
    grid-template-columns: 1fr;
  }
}
</style>
