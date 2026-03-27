<template>
  <div class="page-card">
    <div class="toolbar">
      <div class="title-block">
        <h2>设备管理</h2>
        <p>可查看登录设备并踢出异常会话。</p>
      </div>
      <el-button :loading="loading" @click="loadDevices">刷新设备</el-button>
    </div>

    <el-table :data="devices" v-loading="loading" border>
      <el-table-column label="设备名称" min-width="200">
        <template #default="scope">
          <div class="device-name">
            {{ scope.row.deviceName }}
            <el-tag v-if="scope.row.isCurrent" size="small" type="success">当前设备</el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="deviceType" label="设备类型" width="100" />
      <el-table-column prop="os" label="操作系统" width="110" />
      <el-table-column prop="browser" label="浏览器" width="120" />
      <el-table-column prop="ip" label="IP地址" width="130" />
      <el-table-column label="最后登录时间" width="180">
        <template #default="scope">{{ formatUnixTime(scope.row.lastLoginAt) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="scope">
          <el-button size="small" @click="openDetail(scope.row)">详情</el-button>
          <el-button
            size="small"
            type="danger"
            :disabled="scope.row.isCurrent"
            @click="onKickDevice(scope.row.deviceId)"
          >
            踢出设备
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination">
      <el-pagination
        background
        layout="prev, pager, next, total"
        :current-page="pagination.page"
        :page-size="pagination.pageSize"
        :total="pagination.total"
        @current-change="onPageChange"
      />
    </div>

    <el-drawer v-model="detailVisible" title="设备详情" size="460px">
      <template v-if="selectedDevice">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="设备ID">{{ selectedDevice.deviceId }}</el-descriptions-item>
          <el-descriptions-item label="设备名称">{{ selectedDevice.deviceName }}</el-descriptions-item>
          <el-descriptions-item label="设备类型">{{ selectedDevice.deviceType }}</el-descriptions-item>
          <el-descriptions-item label="操作系统">{{ selectedDevice.os }}</el-descriptions-item>
          <el-descriptions-item label="浏览器">{{ selectedDevice.browser }}</el-descriptions-item>
          <el-descriptions-item label="IP地址">{{ selectedDevice.ip }}</el-descriptions-item>
          <el-descriptions-item label="地理位置">{{ selectedDevice.location }}</el-descriptions-item>
          <el-descriptions-item label="最后登录时间">
            {{ formatUnixTime(selectedDevice.lastLoginAt) }}
          </el-descriptions-item>
        </el-descriptions>

        <h4 class="history-title">登录历史</h4>
        <el-table :data="loginHistory" size="small" border>
          <el-table-column prop="time" label="登录时间" width="170" />
          <el-table-column prop="ip" label="IP" width="130" />
          <el-table-column prop="result" label="结果" width="90" />
        </el-table>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { fetchUserDevices, kickUserDevice } from '../../services/userAuthApi';
import type { DeviceItem } from '../../types/auth';
import { formatUnixTime } from '../../utils/auth';

const loading = ref(false);
const devices = ref<DeviceItem[]>([]);
const detailVisible = ref(false);
const selectedDevice = ref<DeviceItem | null>(null);

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
});

const loginHistory = computed(() => {
  if (!selectedDevice.value) {
    return [];
  }
  return [
    {
      time: formatUnixTime(selectedDevice.value.lastLoginAt),
      ip: selectedDevice.value.ip,
      result: selectedDevice.value.status === 'active' ? '成功' : '已失效'
    }
  ];
});

const loadDevices = async () => {
  try {
    loading.value = true;
    const result = await fetchUserDevices(pagination.page, pagination.pageSize);
    devices.value = result.items;
    pagination.total = result.pagination.total;
  } catch {
    // 错误由拦截器提示
  } finally {
    loading.value = false;
  }
};

const onPageChange = (page: number) => {
  pagination.page = page;
  void loadDevices();
};

const openDetail = (device: DeviceItem) => {
  selectedDevice.value = device;
  detailVisible.value = true;
};

const onKickDevice = async (deviceId: string) => {
  try {
    await ElMessageBox.confirm('确定要踢出该设备吗？该设备的Token将立即失效。', '确认踢出', {
      type: 'warning',
      confirmButtonText: '确认',
      cancelButtonText: '取消'
    });

    await kickUserDevice(deviceId);
    ElMessage.success('设备已踢出');
    await loadDevices();
  } catch {
    // 取消或异常均由组件/拦截器处理
  }
};

onMounted(() => {
  void loadDevices();
});
</script>

<style scoped>
.title-block h2 {
  margin-bottom: 4px;
}

.title-block p {
  margin: 0;
  color: #64748b;
}

.device-name {
  display: flex;
  gap: 8px;
  align-items: center;
}

.history-title {
  margin: 18px 0 10px;
  color: #0f172a;
}
</style>
