<template>
  <div class="branch-diff-view">
    <header class="diff-header">
      <h3>分支差异对比</h3>
      <div class="diff-header-actions">
        <el-tag :type="branchStatusTag" size="small">{{ branchStatusText }}</el-tag>
        <el-button size="small" text @click="$emit('close')">✕</el-button>
      </div>
    </header>

    <div v-if="loading" class="diff-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>加载差异数据...</span>
    </div>

    <template v-else-if="diff">
      <!-- 差异摘要 -->
      <div class="diff-summary">
        <div class="summary-item added">
          <span class="summary-count">+{{ diff.nodes_added.length + diff.edges_added.length }}</span>
          <span class="summary-label">新增</span>
        </div>
        <div class="summary-item removed">
          <span class="summary-count">-{{ diff.nodes_removed.length + diff.edges_removed.length }}</span>
          <span class="summary-label">移除</span>
        </div>
        <div class="summary-item modified">
          <span class="summary-count">~{{ diff.nodes_modified.length }}</span>
          <span class="summary-label">修改</span>
        </div>
      </div>

      <!-- 并排对比 -->
      <div class="diff-panels">
        <!-- 左面板：主工作流 -->
        <div class="diff-panel diff-panel-main">
          <div class="panel-title">
            <el-tag type="info" size="small">主工作流 (main)</el-tag>
          </div>
          <div class="panel-body">
            <!-- 节点列表 -->
            <div class="section-title">节点 ({{ diff.main.nodes.length }})</div>
            <div
              v-for="node in diff.main.nodes"
              :key="node.node_id"
              class="diff-item"
              :class="{
                'diff-removed': diff.nodes_removed.includes(node.node_id),
                'diff-modified': diff.nodes_modified.includes(node.node_id) && selectedNodeId === node.node_id
              }"
              @click="selectNode(node.node_id)"
            >
              <span class="node-kind-badge" :class="`kind-${node.kind}`">{{ node.kind }}</span>
              <span class="node-name">{{ node.name || node.node_id }}</span>
              <span class="node-type">{{ node.node_type }}</span>
            </div>

            <!-- 边列表 -->
            <div class="section-title">边 ({{ diff.main.edges.length }})</div>
            <div
              v-for="edge in diff.main.edges"
              :key="`${edge.source}->${edge.target}`"
              class="diff-item edge-item"
              :class="{
                'diff-removed': diff.edges_removed.includes(`${edge.source}->${edge.target}`)
              }"
            >
              <span>{{ edge.source }}</span>
              <el-icon><Right /></el-icon>
              <span>{{ edge.target }}</span>
              <span v-if="edge.condition" class="edge-condition">{{ edge.condition }}</span>
            </div>
          </div>
        </div>

        <!-- 右面板：分支 -->
        <div class="diff-panel diff-panel-branch">
          <div class="panel-title">
            <el-tag type="warning" size="small">分支 ({{ branchId }})</el-tag>
          </div>
          <div class="panel-body">
            <!-- 节点列表 -->
            <div class="section-title">节点 ({{ diff.branch.nodes.length }})</div>
            <div
              v-for="node in diff.branch.nodes"
              :key="node.node_id"
              class="diff-item"
              :class="{
                'diff-added': diff.nodes_added.includes(node.node_id),
                'diff-modified': diff.nodes_modified.includes(node.node_id) && selectedNodeId === node.node_id
              }"
              @click="selectNode(node.node_id)"
            >
              <span class="node-kind-badge" :class="`kind-${node.kind}`">{{ node.kind }}</span>
              <span class="node-name">{{ node.name || node.node_id }}</span>
              <span class="node-type">{{ node.node_type }}</span>
            </div>

            <!-- 边列表 -->
            <div class="section-title">边 ({{ diff.branch.edges.length }})</div>
            <div
              v-for="edge in diff.branch.edges"
              :key="`${edge.source}->${edge.target}`"
              class="diff-item edge-item"
              :class="{
                'diff-added': diff.edges_added.includes(`${edge.source}->${edge.target}`)
              }"
            >
              <span>{{ edge.source }}</span>
              <el-icon><Right /></el-icon>
              <span>{{ edge.target }}</span>
              <span v-if="edge.condition" class="edge-condition">{{ edge.condition }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 选中节点的详细参数对比 -->
      <div v-if="selectedNodeDetail" class="node-detail-compare">
        <div class="section-title">节点参数对比: {{ selectedNodeId }}</div>
        <el-table :data="nodeParamRows" size="small" border>
          <el-table-column prop="param" label="参数" width="160" />
          <el-table-column prop="mainValue" label="主工作流">
            <template #default="{ row }">
              <span :class="{ 'value-changed': row.changed }">{{ row.mainValue }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="branchValue" label="分支">
            <template #default="{ row }">
              <span :class="{ 'value-changed': row.changed }">{{ row.branchValue }}</span>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 操作按钮 -->
      <div class="diff-actions" v-if="branchStatus === 'open'">
        <el-button type="primary" :loading="merging" @click="handleMerge">
          确认合并到主工作流
        </el-button>
        <el-button type="danger" plain :loading="rejecting" @click="handleReject">
          拒绝此分支
        </el-button>
      </div>
    </template>

    <div v-else class="diff-empty">
      <p>无法加载差异数据</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Right, Loading } from '@element-plus/icons-vue';
import { workflowService } from '../../services/WorkflowService';
import type { WorkflowBranchDiff, WorkflowNodeDefinition } from '../../types/workflow';

interface Props {
  branchId: string;
  workflowId: string;
  resolverUserId: string;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  close: [];
  merged: [];
  rejected: [];
}>();

const loading = ref(false);
const merging = ref(false);
const rejecting = ref(false);
const diff = ref<WorkflowBranchDiff | null>(null);
const selectedNodeId = ref<string | null>(null);

const branchStatus = ref<string>('open');

const branchStatusTag = computed(() => {
  if (branchStatus.value === 'open') return 'warning';
  if (branchStatus.value === 'merged') return 'success';
  return 'danger';
});

const branchStatusText = computed(() => {
  if (branchStatus.value === 'open') return '待处理';
  if (branchStatus.value === 'merged') return '已合并';
  return '已拒绝';
});

const selectedNodeDetail = computed(() => {
  if (!diff.value || !selectedNodeId.value) return null;
  const mainNode = diff.value.main.nodes.find(n => n.node_id === selectedNodeId.value);
  const branchNode = diff.value.branch.nodes.find(n => n.node_id === selectedNodeId.value);
  if (!mainNode && !branchNode) return null;
  const mainParams = mainNode?.params || {};
  const branchParams = branchNode?.params || {};
  // 合并所有参数名
  const allKeys = new Set([...Object.keys(mainParams), ...Object.keys(branchParams)]);
  const rows = Array.from(allKeys).map(key => {
    const mv = JSON.stringify(mainParams[key] ?? '(无)');
    const bv = JSON.stringify(branchParams[key] ?? '(无)');
    return { param: key, mainValue: mv, branchValue: bv, changed: mv !== bv };
  });
  return rows;
});

const nodeParamRows = computed(() => selectedNodeDetail.value || []);

function selectNode(nodeId: string) {
  selectedNodeId.value = selectedNodeId.value === nodeId ? null : nodeId;
}

async function fetchDiff() {
  loading.value = true;
  try {
    diff.value = await workflowService.getBranchDiff(props.branchId);
    const branch = await workflowService.getBranch(props.branchId);
    branchStatus.value = branch.status;
  } catch (e: any) {
    ElMessage.error(`加载差异失败: ${e?.message || e}`);
  } finally {
    loading.value = false;
  }
}

async function handleMerge() {
  try {
    await ElMessageBox.confirm(
      '确认将分支的所有更改合并到主工作流吗？此操作不可撤销。',
      '确认合并',
      { confirmButtonText: '确认合并', cancelButtonText: '取消', type: 'warning' }
    );
  } catch {
    return;
  }

  merging.value = true;
  try {
    await workflowService.mergeBranch(props.branchId, {
      resolver_user_id: props.resolverUserId,
    });
    ElMessage.success('分支已成功合并到主工作流');
    branchStatus.value = 'merged';
    emit('merged');
  } catch (e: any) {
    ElMessage.error(`合并失败: ${e?.message || e}`);
  } finally {
    merging.value = false;
  }
}

async function handleReject() {
  try {
    await ElMessageBox.confirm(
      '确认拒绝此分支吗？分支数据将保留但不会合并到主工作流。',
      '确认拒绝',
      { confirmButtonText: '确认拒绝', cancelButtonText: '取消', type: 'warning' }
    );
  } catch {
    return;
  }

  rejecting.value = true;
  try {
    await workflowService.rejectBranch(props.branchId, {
      resolver_user_id: props.resolverUserId,
    });
    ElMessage.success('分支已被拒绝');
    branchStatus.value = 'rejected';
    emit('rejected');
  } catch (e: any) {
    ElMessage.error(`操作失败: ${e?.message || e}`);
  } finally {
    rejecting.value = false;
  }
}

watch(() => props.branchId, () => {
  if (props.branchId) fetchDiff();
}, { immediate: true });
</script>

<style scoped>
.branch-diff-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;
}

.diff-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
}

.diff-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
}

.diff-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.diff-loading,
.diff-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 60px 20px;
  color: #94a3b8;
}

.diff-summary {
  display: flex;
  gap: 16px;
  padding: 12px 20px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
}

.summary-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.summary-count {
  font-weight: 700;
  font-size: 18px;
}

.summary-item.added .summary-count { color: #22c55e; }
.summary-item.removed .summary-count { color: #ef4444; }
.summary-item.modified .summary-count { color: #f59e0b; }

.summary-label {
  font-size: 12px;
  color: #64748b;
}

.diff-panels {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0;
  flex: 1;
  overflow: hidden;
  border-bottom: 1px solid #e2e8f0;
}

.diff-panel {
  overflow-y: auto;
  border-right: 1px solid #e2e8f0;
}

.diff-panel:last-child {
  border-right: none;
}

.panel-title {
  padding: 10px 16px;
  background: #f1f5f9;
  border-bottom: 1px solid #e2e8f0;
  position: sticky;
  top: 0;
  z-index: 1;
}

.panel-body {
  padding: 8px;
}

.section-title {
  font-size: 11px;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  padding: 8px 4px 4px;
  letter-spacing: 0.5px;
}

.diff-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  transition: background 150ms;
}

.diff-item:hover {
  background: #f1f5f9;
}

.diff-item.diff-added {
  background: #f0fdf4;
  border-left: 3px solid #22c55e;
}

.diff-item.diff-removed {
  background: #fef2f2;
  border-left: 3px solid #ef4444;
  text-decoration: line-through;
  opacity: 0.7;
}

.diff-item.diff-modified {
  background: #fffbeb;
  border-left: 3px solid #f59e0b;
}

.edge-item {
  font-family: monospace;
  font-size: 12px;
}

.edge-condition {
  color: #64748b;
  font-size: 11px;
  margin-left: auto;
}

.node-kind-badge {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  color: #fff;
}

.kind-input { background: #3b82f6; }
.kind-process { background: #8b5cf6; }
.kind-output { background: #22c55e; }
.kind-control { background: #f59e0b; }

.node-name {
  font-weight: 500;
}

.node-type {
  color: #94a3b8;
  font-size: 11px;
  margin-left: auto;
}

.node-detail-compare {
  padding: 16px 20px;
  border-bottom: 1px solid #e2e8f0;
  max-height: 300px;
  overflow-y: auto;
}

.value-changed {
  background: #fef3c7;
  padding: 1px 4px;
  border-radius: 2px;
  font-weight: 500;
}

.diff-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 20px;
  flex-shrink: 0;
  border-top: 1px solid #e2e8f0;
}
</style>
