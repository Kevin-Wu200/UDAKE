<template>
  <div class="page-card">
    <div class="toolbar">
      <el-date-picker
        v-model="timeRange"
        type="datetimerange"
        range-separator="至"
        start-placeholder="开始时间"
        end-placeholder="结束时间"
        value-format="YYYY-MM-DD HH:mm:ss"
      />
      <el-select v-model="eventType" clearable placeholder="事件类型" style="width: 170px">
        <el-option label="创建密钥" value="create_key" />
        <el-option label="导入密钥" value="import_key" />
        <el-option label="更新用户" value="update_user" />
        <el-option label="重置密码" value="reset_password" />
        <el-option label="登录" value="login" />
        <el-option label="删除密钥" value="delete_key" />
      </el-select>
      <el-input v-model="keyword" clearable placeholder="搜索操作人/对象" style="width: 220px" />
      <el-button type="primary" @click="search">查询</el-button>
      <el-button @click="resetSearch">重置</el-button>
      <el-dropdown @command="onExport">
        <el-button type="success">
          导出日志 ▼
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="csv">导出 CSV（最多10000）</el-dropdown-item>
            <el-dropdown-item command="json">导出 JSON（最多10000）</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>

    <el-table :data="list" border>
      <el-table-column prop="operator" label="操作人" min-width="140" />
      <el-table-column prop="eventType" label="操作类型" width="140">
        <template #default="scope">{{ eventText(scope.row.eventType) }}</template>
      </el-table-column>
      <el-table-column prop="target" label="操作对象" min-width="240" />
      <el-table-column prop="time" label="操作时间" width="180" />
      <el-table-column prop="ip" label="IP地址" width="150" />
    </el-table>

    <div class="pagination">
      <el-pagination
        background
        layout="total, prev, pager, next, sizes"
        :current-page="page"
        :page-size="pageSize"
        :page-sizes="[10, 20, 50]"
        :total="total"
        @current-change="onPageChange"
        @size-change="onPageSizeChange"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { AuditEventType, AuditLog } from '../types/admin';
import { onMounted, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { fetchAuditLogs, fetchAuditLogsForExport } from '../services/mockApi';

const list = ref<AuditLog[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(10);
const keyword = ref('');
const eventType = ref<AuditEventType>();
const timeRange = ref<[string, string] | null>(null);

const eventText = (type: AuditEventType) => {
  const map: Record<AuditEventType, string> = {
    create_key: '创建密钥',
    import_key: '导入密钥',
    update_user: '更新用户',
    reset_password: '重置密码',
    login: '登录',
    delete_key: '删除密钥'
  };
  return map[type];
};

const getQuery = () => ({
  eventType: eventType.value,
  keyword: keyword.value,
  startTime: timeRange.value?.[0],
  endTime: timeRange.value?.[1]
});

const loadList = async () => {
  try {
    const res = await fetchAuditLogs({
      page: page.value,
      pageSize: pageSize.value,
      ...getQuery()
    });
    list.value = res.items;
    total.value = res.total;
  } catch {
    ElMessage.error('获取审计日志失败');
  }
};

const search = () => {
  page.value = 1;
  loadList();
};

const resetSearch = () => {
  keyword.value = '';
  eventType.value = undefined;
  timeRange.value = null;
  page.value = 1;
  loadList();
};

const onPageChange = (nextPage: number) => {
  page.value = nextPage;
  loadList();
};

const onPageSizeChange = (size: number) => {
  pageSize.value = size;
  page.value = 1;
  loadList();
};

const downloadFile = (fileName: string, content: string, type: string) => {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = fileName;
  a.click();
  URL.revokeObjectURL(url);
};

const toCSV = (rows: AuditLog[]) => {
  const header = ['操作人', '操作类型', '操作对象', '操作时间', 'IP地址'];
  const body = rows.map((item) => [item.operator, eventText(item.eventType), item.target, item.time, item.ip]);
  return [header, ...body]
    .map((row) => row.map((cell) => `"${String(cell).split('"').join('""')}"`).join(','))
    .join('\n');
};

const onExport = async (command: 'csv' | 'json') => {
  try {
    const rows = await fetchAuditLogsForExport(getQuery());
    if (rows.length > 10000) {
      ElMessage.warning('导出已被限制为最多 10000 条');
      return;
    }

    const now = new Date().toISOString().slice(0, 19).split(':').join('-');
    if (command === 'csv') {
      downloadFile(`audit-logs-${now}.csv`, toCSV(rows), 'text/csv;charset=utf-8;');
    } else {
      downloadFile(`audit-logs-${now}.json`, JSON.stringify(rows, null, 2), 'application/json');
    }

    ElMessage.success('导出成功');
  } catch {
    ElMessage.error('导出失败');
  }
};

onMounted(() => {
  loadList();
});
</script>
