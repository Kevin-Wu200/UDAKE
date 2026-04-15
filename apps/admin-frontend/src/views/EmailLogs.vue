<template>
  <div class="email-logs-view">
    <el-card class="filter-card">
      <el-form :inline="true" :model="filterForm">
        <el-form-item label="发送状态">
          <el-select v-model="filterForm.status" clearable style="width: 160px" placeholder="全部状态">
            <el-option label="成功" value="success" />
            <el-option label="失败" value="failed" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="timeRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            value-format="YYYY-MM-DD HH:mm:ss"
            style="width: 360px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">搜索</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-table :data="logs" border v-loading="loading">
      <el-table-column prop="sent_at" label="发送时间" width="180" />
      <el-table-column prop="recipient" label="收件人" min-width="220" />
      <el-table-column prop="subject" label="邮件主题" min-width="220" />
      <el-table-column label="发送状态" width="120">
        <template #default="{ row }">
          <el-tag :type="row.status === 'success' ? 'success' : 'danger'">
            {{ row.status === 'success' ? '成功' : '失败' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="失败原因" min-width="220">
        <template #default="{ row }">
          <span class="failure-text">{{ row.failure_reason || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" :disabled="!row.retryable" @click="handleResend(row.id)">重发</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination">
      <el-pagination
        background
        layout="total, prev, pager, next, sizes"
        :current-page="pagination.page"
        :page-size="pagination.pageSize"
        :page-sizes="[10, 20, 50]"
        :total="pagination.total"
        @current-change="handlePageChange"
        @size-change="handleSizeChange"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { EmailLog, EmailSendStatus } from '../types/admin';
import { onMounted, reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { fetchEmailLogs, resendEmailLog } from '../services/mockApi';

const loading = ref(false);
const logs = ref<EmailLog[]>([]);
const timeRange = ref<[string, string] | []>([]);

const filterForm = reactive<{
  status?: EmailSendStatus;
}>({
  status: undefined
});

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
});

const loadLogs = async () => {
  loading.value = true;
  try {
    const res = await fetchEmailLogs({
      page: pagination.page,
      pageSize: pagination.pageSize,
      status: filterForm.status,
      startTime: timeRange.value[0] || undefined,
      endTime: timeRange.value[1] || undefined
    });
    logs.value = res.items;
    pagination.total = res.total;
  } catch {
    ElMessage.error('加载邮件日志失败');
  } finally {
    loading.value = false;
  }
};

const handleSearch = () => {
  pagination.page = 1;
  void loadLogs();
};

const handleReset = () => {
  filterForm.status = undefined;
  timeRange.value = [];
  pagination.page = 1;
  void loadLogs();
};

const handlePageChange = (nextPage: number) => {
  pagination.page = nextPage;
  void loadLogs();
};

const handleSizeChange = (nextSize: number) => {
  pagination.pageSize = nextSize;
  pagination.page = 1;
  void loadLogs();
};

const handleResend = async (id: number) => {
  try {
    await resendEmailLog(id);
    ElMessage.success('重发任务已提交');
    await loadLogs();
  } catch {
    ElMessage.error('重发失败');
  }
};

onMounted(() => {
  void loadLogs();
});
</script>

<style scoped>
.email-logs-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.pagination {
  display: flex;
  justify-content: flex-end;
}

.failure-text {
  color: #b91c1c;
}
</style>
