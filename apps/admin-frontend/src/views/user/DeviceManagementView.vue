<template>
  <div class="page-card">
    <div class="toolbar">
      <div class="title-block">
        <h2>{{ t('deviceManagement') }}</h2>
        <p>{{ t('deviceManagementDescription') }}</p>
      </div>
      <el-button :loading="loading" @click="loadDevices">{{ t('refreshDevices') }}</el-button>
    </div>

    <el-table :data="devices" v-loading="loading" border>
      <el-table-column :label="t('deviceName')" min-width="200">
        <template #default="scope">
          <div class="device-name">
            {{ scope.row.deviceName }}
            <el-tag v-if="scope.row.isCurrent" size="small" type="success">{{ t('currentDevice') }}</el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="deviceType" :label="t('deviceType')" width="100" />
      <el-table-column prop="os" :label="t('osLabel')" width="110" />
      <el-table-column prop="browser" :label="t('browser')" width="120" />
      <el-table-column prop="ip" :label="t('ipAddress')" width="130" />
      <el-table-column :label="t('lastLoginTime')" width="180">
        <template #default="scope">{{ formatUnixTime(scope.row.lastLoginAt) }}</template>
      </el-table-column>
      <el-table-column :label="t('actions')" width="220" fixed="right">
        <template #default="scope">
          <el-button size="small" @click="openDetail(scope.row)">{{ t('details') }}</el-button>
          <el-button
            size="small"
            type="danger"
            :disabled="scope.row.isCurrent"
            @click="onKickDevice(scope.row.deviceId)"
          >
            {{ t('kickDevice') }}
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

    <el-drawer v-model="detailVisible" :title="t('deviceDetail')" size="460px">
      <template v-if="selectedDevice">
        <el-descriptions :column="1" border>
          <el-descriptions-item :label="t('deviceId')">{{ selectedDevice.deviceId }}</el-descriptions-item>
          <el-descriptions-item :label="t('deviceName')">{{ selectedDevice.deviceName }}</el-descriptions-item>
          <el-descriptions-item :label="t('deviceType')">{{ selectedDevice.deviceType }}</el-descriptions-item>
          <el-descriptions-item :label="t('osLabel')">{{ selectedDevice.os }}</el-descriptions-item>
          <el-descriptions-item :label="t('browser')">{{ selectedDevice.browser }}</el-descriptions-item>
          <el-descriptions-item :label="t('ipAddress')">{{ selectedDevice.ip }}</el-descriptions-item>
          <el-descriptions-item :label="t('location')">{{ selectedDevice.location }}</el-descriptions-item>
          <el-descriptions-item :label="t('lastLoginTime')">
            {{ formatUnixTime(selectedDevice.lastLoginAt) }}
          </el-descriptions-item>
        </el-descriptions>

        <h4 class="history-title">{{ t('loginHistory') }}</h4>
        <el-table :data="loginHistory" size="small" border>
          <el-table-column prop="time" :label="t('time')" width="170" />
          <el-table-column prop="ip" label="IP" width="130" />
          <el-table-column prop="result" :label="t('result')" width="90" />
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
import { useI18nText } from '../../i18n/useI18n';

const { t } = useI18nText();

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
      result: selectedDevice.value.status === 'active' ? t('success') : t('expired')
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
    await ElMessageBox.confirm(t('kickDeviceConfirm'), t('kickDeviceConfirmTitle'), {
      type: 'warning',
      confirmButtonText: t('confirm'),
      cancelButtonText: t('cancel'),
      modalClass: 'admin-confirm-dialog-overlay',
      closeOnClickModal: false,
      closeOnPressEscape: false
    });

    await kickUserDevice(deviceId);
    ElMessage.success(t('deviceKicked'));
    await loadDevices();
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      console.error(t('kickDeviceFailed'), error);
      ElMessage.error(t('actionfailed'));
    }
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
