<template>
  <div class="page-card">
    <div class="toolbar">
      <div class="title-block">
        <h2>{{t('divice.Management')}}</h2>
        <p>{{t('divice.p')}}</p>
      </div>
      <el-button :loading="loading" @click="loadDevices">{{t('divice.refresh')}}</el-button>
    </div>

    <el-table :data="devices" v-loading="loading" border>
      <el-table-column :label="t('divice.name')" min-width="200">
        <template #default="scope">
          <div class="device-name">
            {{ scope.row.deviceName }}
            <el-tag v-if="scope.row.isCurrent" size="small" type="success">{{t('divice.now')}}</el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="deviceType" :label="t('divice.type')" width="100" />
      <el-table-column prop="os" :label="t('divice.OS')" width="110" />
      <el-table-column prop="browser" :label="t('divice.browser')" width="120" />
      <el-table-column prop="ip" :label="t('divice.IP')" width="130" />
      <el-table-column :label="t('divice.LastLoginTime')" width="180">
        <template #default="scope">{{ formatUnixTime(scope.row.lastLoginAt) }}</template>
      </el-table-column>
      <el-table-column :label="t('divice.operation')" width="220" fixed="right">
        <template #default="scope">
          <el-button size="small" @click="openDetail(scope.row)">{{t('divice.Details')}}</el-button>
          <el-button
            size="small"
            type="danger"
            :disabled="scope.row.isCurrent"
            @click="onKickDevice(scope.row.deviceId)"
          >
            {{t('divice.KickDivice')}}
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

    <el-drawer v-model="detailVisible" :title="t('divice.DivicsDetails')" size="460px">
      <template v-if="selectedDevice">
        <el-descriptions :column="1" border>
          <el-descriptions-item :label="t('divice.ID')">{{ selectedDevice.deviceId }}</el-descriptions-item>
          <el-descriptions-item :label="t('divice.name')">{{ selectedDevice.deviceName }}</el-descriptions-item>
          <el-descriptions-item :label="t('divice.type')">{{ selectedDevice.deviceType }}</el-descriptions-item>
          <el-descriptions-item :label="t('divice.OS')">{{ selectedDevice.os }}</el-descriptions-item>
          <el-descriptions-item :label="t('divice.browser')">{{ selectedDevice.browser }}</el-descriptions-item>
          <el-descriptions-item :label="t('divice.IP')">{{ selectedDevice.ip }}</el-descriptions-item>
          <el-descriptions-item :label="t('divice.GeographicalLocation')">{{ selectedDevice.location }}</el-descriptions-item>
          <el-descriptions-item :label="t('divice.LastLoginTime')">
            {{ formatUnixTime(selectedDevice.lastLoginAt) }}
          </el-descriptions-item>
        </el-descriptions>

        <h4 class="history-title">{{ t('divice.LoginHistory') }}</h4>
        <el-table :data="loginHistory" size="small" border>
          <el-table-column prop="time" :label="t('divice.LoginTime')" width="170" />
          <el-table-column prop="ip" label="IP" width="130" />
          <el-table-column prop="result" :label="t('divice.result')" width="90" />
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
import { useI18nText_user } from '../../i18n/useI18n';

const { t } = useI18nText_user();

interface EmailForm {
  newEmail: string;
  currentPassword: string;
  code: string;
}

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
      result: selectedDevice.value.status === 'active' ? t('divice.Success') : t('divice.Expired')
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
    await ElMessageBox.confirm(t('divice.sure'), t('divice.ConfirmKick'), {
      type: 'warning',
      confirmButtonText: t('divice.Confirm'),
      cancelButtonText: t('divice.Cancel'),
      modalClass: 'admin-confirm-dialog-overlay',
      closeOnClickModal: false,
      closeOnPressEscape: false
    });

    await kickUserDevice(deviceId);
    ElMessage.success(t('divice.DiviceKicked'));
    await loadDevices();
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      console.error(t('divice.failed'), error);
      ElMessage.error(t('divice.again'));
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
