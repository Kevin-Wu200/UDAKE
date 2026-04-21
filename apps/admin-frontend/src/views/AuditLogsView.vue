<template>
  <div class="page-card">
    <div class="toolbar">
      <el-date-picker
        v-model="timeRange"
        type="datetimerange"
        :range-separator="t('to')"
        :start-placeholder="t('starttime')"
        :end-placeholder="t('endtime')"
        value-format="YYYY-MM-DD HH:mm:ss"
      />
      <el-select v-model="eventType" clearable :placeholder="t('issuetype')" style="width: 170px">
        <el-option :label="t('createkey')" value="create_key" />
        <el-option :label="t('importkey')" value="import_key" />
        <el-option :label="t('updateuser')" value="update_user" />
        <el-option :label="t('resetpw')" value="reset_password" />
        <el-option :label="t('login')" value="login" />
        <el-option :label="t('deletekey')" value="delete_key" />
      </el-select>
      <el-input v-model="keyword" clearable :placeholder="t('searchoperator')" style="width: 220px" />
      <el-button type="primary" @click="search">{{ t('query') }}</el-button>
      <el-button @click="resetSearch">{{ t('reset') }}</el-button>
      <el-dropdown @command="onExport">
        <el-button type="success">
          {{ t('exportlog') }} ▼
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="csv">{{ t('export') }} CSV（{{ t('max') }}10000）</el-dropdown-item>
            <el-dropdown-item command="json">{{ t('export') }} JSON（{{ t('max') }}10000）</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>

    <el-table :data="list" border>
      <el-table-column prop="operator" :label="t('operator')" min-width="140" />
      <el-table-column prop="eventType" :label="t('operatetype')" width="140">
        <template #default="scope">{{ eventText(scope.row.eventType) }}</template>
      </el-table-column>
      <el-table-column prop="target" :label="t('operateobj')" min-width="240" />
      <el-table-column prop="time" :label="t('operatetime')" width="180" />
      <el-table-column prop="ip" :label="t('ipaddr')" width="150" />
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
import { fetchAuditLogs, fetchAuditLogsForExport } from '../services/http';
import { useI18nText } from '../i18n/useI18n';

const { t } = useI18nText();
const list = ref<AuditLog[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(10);
const keyword = ref('');
const eventType = ref<AuditEventType>();
const timeRange = ref<[string, string] | null>(null);

const eventText = (type: AuditEventType) => {
  const map: Record<AuditEventType, string> = {
    create_key: t('createkey'),
    import_key: t('importkey'),
    update_user: t('updateuser'),
    reset_password: t('resetpw'),
    login: t('login'),
    delete_key: t('deletekey')
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
    ElMessage.error(t('fetchauditlogfailed'));
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
  const header = [t('operator'), t('operatetype'), t('operateobj'), t('operatetime'), t('ipaddr')];
  const body = rows.map((item) => [item.operator, eventText(item.eventType), item.target, item.time, item.ip]);
  return [header, ...body]
    .map((row) => row.map((cell) => `"${String(cell).split('"').join('""')}"`).join(','))
    .join('\n');
};

const onExport = async (command: 'csv' | 'json') => {
  try {
    const rows = await fetchAuditLogsForExport(getQuery());
    if (rows.length > 10000) {
      ElMessage.warning(t('exportlimit'));
      return;
    }

    const now = new Date().toISOString().slice(0, 19).split(':').join('-');
    if (command === 'csv') {
      downloadFile(`audit-logs-${now}.csv`, toCSV(rows), 'text/csv;charset=utf-8;');
    } else {
      downloadFile(`audit-logs-${now}.json`, JSON.stringify(rows, null, 2), 'application/json');
    }

    ElMessage.success(t('exportsuccess'));
  } catch {
    ElMessage.error(t('exportfailed'));
  }
};

onMounted(() => {
  loadList();
});
</script>
