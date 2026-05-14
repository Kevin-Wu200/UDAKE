<template>
  <div class="company-product-keys-view">
    <div class="page-header">
      <h1>{{ t('companyProductKeys') }}</h1>
      <div class="company-info">
        <el-tag type="success">{{ currentCompany.name }}</el-tag>
        <el-tag type="warning">{{ tc('manager') }}{{ adminTypeLabel }}</el-tag>
        <el-tag type="info">{{ t('companykey') }}{{ companyStats.totalKeys }} / {{ createLimit }}</el-tag>
      </div>
    </div>

    <div class="stats-cards">
      <el-card class="stat-card">
        <div class="stat-value">{{ companyStats.totalKeys }}</div>
        <div class="stat-label">{{ t('totalkeys') }}</div>
      </el-card>
      <el-card class="stat-card">
        <div class="stat-value">{{ companyStats.activeKeys }}</div>
        <div class="stat-label">{{ t('activeKeys') }}</div>
      </el-card>
      <el-card class="stat-card">
        <div class="stat-value">{{ companyStats.assignedKeys }}</div>
        <div class="stat-label">{{ tc('assignedKey') }}</div>
      </el-card>
      <el-card class="stat-card">
        <div class="stat-value">{{ companyStats.availableKeys }}</div>
        <div class="stat-label">{{ t('unusedKeys') }}</div>
      </el-card>
      <el-card class="stat-card">
        <div class="stat-value">{{ companyStats.expiredKeys }}</div>
        <div class="stat-label">{{ t('expired') }}</div>
      </el-card>
    </div>

    <div class="action-bar">
      <el-button type="primary" @click="handleBatchGenerate">{{ tc('batchGenerateCompanyKeys') }}</el-button>
      <el-button @click="handleAssignKey">{{ tc('assignedKey') }}</el-button>
      <el-button @click="handleViewUsers">{{ tc('menbermanage') }}</el-button>
    </div>

    <el-card class="filter-card">
      <el-form :inline="true" :model="filterForm">
        <el-form-item :label="t('keytype')">
          <el-select v-model="filterForm.type" :placeholder="t('selectType')" clearable style="width: 180px">
            <el-option :label="tc('companyTrail')" value="enterprise_trial" />
            <el-option :label="tc('companyStandard')" value="enterprise_standard" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('assignedat')">
          <el-select v-model="filterForm.assigned" :placeholder="t('selectStatus')" clearable style="width: 160px">
            <el-option :label="tc('assignedKey')" :value="true" />
            <el-option :label="t('unused')" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">{{ t('search') }}</el-button>
          <el-button @click="handleReset">{{ t('reset') }}</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-table :data="keys" border v-loading="loading">
      <el-table-column prop="product_key" :label="t('key')" min-width="220" />
      <el-table-column prop="key_type" :label="t('type')" width="120">
        <template #default="{ row }">{{ getKeyTypeLabel(row.key_type) }}</template>
      </el-table-column>
      <el-table-column prop="status" :label="t('status')" width="110">
        <template #default="{ row }">
          <el-tag :type="getStatusType(row.status)">{{ getStatusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="total_quota" :label="t('totalquota')" width="100" />
      <el-table-column prop="used_count" :label="t('used')" width="100" />
      <el-table-column :label="tc('assignedKey')" width="180">
        <template #default="{ row }">{{ row.metadata?.assigned_user_name || '-' }}</template>
      </el-table-column>
      <el-table-column prop="assigned_at" :label="t('assignedat')" width="170" />
      <el-table-column prop="expires_at" :label="t('expiresat')" width="180">
        <template #default="{ row }">
          <span :class="{ 'is-expired-time': row.status === 'expired' }">{{ row.expires_at || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column :label="t('actions')" width="220" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="handleView(row)">{{ t('check') }}</el-button>
          <el-button
            link
            type="primary"
            @click="handleAssign(row)"
            :disabled="Boolean(row.metadata?.assigned_user_name)"
          >
            {{ tc('assignedKey') }}
          </el-button>
          <el-button
            link
            type="danger"
            @click="handleRevoke(row)"
            :disabled="!row.metadata?.assigned_user_name"
          >
            {{ t('cancel') }}
          </el-button>
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

    <key-generate-dialog
      v-model="generateDialogVisible"
      :available-types="companyAdminProfile?.allowed_key_types"
      :remaining-quota="companyAdminProfile?.remaining_keys_quota"
      @success="handleGenerateSuccess"
    />

    <el-dialog v-model="assignDialogVisible" :title="tc('assignedKey')" width="460px">
      <el-form ref="assignFormRef" :model="assignForm" :rules="assignRules" label-width="100px">
        <el-form-item :label="t('userid')" prop="user_id">
          <el-select v-model="assignForm.user_id" :placeholder="t('selectUser')" filterable style="width: 100%">
            <el-option v-for="user in companyUsers" :key="user.id" :label="user.name" :value="user.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assignDialogVisible = false">{{ tc('cancel') }}</el-button>
        <el-button type="primary" @click="confirmAssign">{{ tc('confirm') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="detailDialogVisible" :title="t('keydetail')" width="640px">
      <el-descriptions :column="2" border v-if="selectedKey">
        <el-descriptions-item :label="t('key')">{{ selectedKey.product_key }}</el-descriptions-item>
        <el-descriptions-item :label="t('type')">{{ getKeyTypeLabel(selectedKey.key_type) }}</el-descriptions-item>
        <el-descriptions-item :label="t('status')">{{ getStatusLabel(selectedKey.status) }}</el-descriptions-item>
        <el-descriptions-item :label="t('totalquota')">{{ selectedKey.total_quota }}</el-descriptions-item>
        <el-descriptions-item :label="t('used')">{{ selectedKey.used_count }}</el-descriptions-item>
        <el-descriptions-item :label="tc('assignedKey')">
          {{ selectedKey.metadata?.assigned_user_name || '-' }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('expiresat')">{{ selectedKey.expires_at || '-' }}</el-descriptions-item>
        <el-descriptions-item :label="t('assignedat')">{{ selectedKey.assigned_at || '-' }}</el-descriptions-item>
        <el-descriptions-item :label="t('notes')">{{ selectedKey.metadata?.notes || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import type { FormInstance, FormRules } from 'element-plus';
import type { CompanyAdmin, KeyStatus, ProductKey } from '../types/admin';
import { computed, onMounted, reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { useRouter } from 'vue-router';
import { useAuthStore } from '../stores/auth';
import KeyGenerateDialog from '../components/KeyGenerateDialog.vue';
import {
  assignCompanyKey,
  fetchCompanyAdminProfile,
  fetchCompanyKeyStats,
  fetchCompanyKeys,
  fetchCompanyUsers,
  revokeCompanyKey
} from '../services/http';
import { useI18nText } from '../i18n/useI18n';

const { t, tc } = useI18nText();

const router = useRouter();
const authStore = useAuthStore();
const currentCompany = computed(() => authStore.currentCompany);
const loading = ref(false);
const keys = ref<ProductKey[]>([]);
const selectedKey = ref<ProductKey | null>(null);

const filterForm = reactive<{
  type?: 'enterprise_trial' | 'enterprise_standard';
  assigned?: boolean;
}>({
  type: undefined,
  assigned: undefined
});

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
});

const companyStats = reactive({
  totalKeys: 0,
  activeKeys: 0,
  assignedKeys: 0,
  availableKeys: 0,
  expiredKeys: 0
});

const companyAdminProfile = ref<CompanyAdmin | null>(null);
const adminTypeLabel = computed(() =>
  companyAdminProfile.value?.company_admin_type === 'trial' ? t('companyAdminTrial') : t('companyAdminStandard')
);
const createLimit = computed(() => companyAdminProfile.value?.max_keys_allowed ?? 1000);

const generateDialogVisible = ref(false);
const assignDialogVisible = ref(false);
const detailDialogVisible = ref(false);
const assignFormRef = ref<FormInstance>();
const assignKeyId = ref<number>(0);
const companyUsers = ref<Array<{ id: number; name: string }>>([]);
const assignForm = reactive({
  user_id: undefined as number | undefined
});

const assignRules: FormRules<typeof assignForm> = {
  user_id: [{ required: true, message: t('selectUser'), trigger: 'change' }]
};

const getKeyTypeLabel = (type: ProductKey['key_type']) =>
  type === 'enterprise_trial' ? tc('companyTrail') : tc('companyStandard');

const getStatusLabel = (status: KeyStatus) => {
  const map: Record<KeyStatus, string> = {
    unused: t('unused'),
    active: t('active'),
    disabled: t('disabled'),
    expired: t('expired')
  };
  return map[status];
};

const getStatusType = (status: KeyStatus): 'success' | 'warning' | 'info' | 'danger' => {
  if (status === 'active') {
    return 'success';
  }
  if (status === 'disabled') {
    return 'warning';
  }
  if (status === 'expired') {
    return 'danger';
  }
  return 'info';
};

const loadCompanyStats = async () => {
  const res = await fetchCompanyKeyStats(currentCompany.value.id);
  companyStats.totalKeys = res.totalKeys;
  companyStats.activeKeys = res.activeKeys;
  companyStats.assignedKeys = res.assignedKeys;
  companyStats.availableKeys = res.availableKeys;
  companyStats.expiredKeys = keys.value.filter((item) => item.status === 'expired').length;
};

const loadCompanyUsers = async () => {
  companyUsers.value = await fetchCompanyUsers(currentCompany.value.id);
};

const loadCompanyProfile = async () => {
  try {
    companyAdminProfile.value = await fetchCompanyAdminProfile(currentCompany.value.id);
  } catch {
    companyAdminProfile.value = null;
  }
};

const loadList = async () => {
  loading.value = true;
  try {
    const res = await fetchCompanyKeys({
      page: pagination.page,
      pageSize: pagination.pageSize,
      company_id: currentCompany.value.id,
      type: filterForm.type,
      assigned: filterForm.assigned
    });
    keys.value = res.items;
    pagination.total = res.total;
  } catch {
    ElMessage.error(t('loadKeyListFailed'));
  } finally {
    loading.value = false;
  }
};

const handleBatchGenerate = () => {
  generateDialogVisible.value = true;
};

const handleAssignKey = () => {
  const target = keys.value.find((item) => !item.metadata?.assigned_user_name);
  if (!target) {
    ElMessage.warning(t('noKeyToAssign'));
    return;
  }
  handleAssign(target);
};

const handleViewUsers = () => {
  void router.push('/users');
};

const handleSearch = async () => {
  pagination.page = 1;
  await loadList();
};

const handleReset = async () => {
  filterForm.type = undefined;
  filterForm.assigned = undefined;
  pagination.page = 1;
  await loadList();
};

const handlePageChange = (nextPage: number) => {
  pagination.page = nextPage;
  void loadList();
};

const handleSizeChange = (nextSize: number) => {
  pagination.pageSize = nextSize;
  pagination.page = 1;
  void loadList();
};

const handleGenerateSuccess = async () => {
  await Promise.all([loadList(), loadCompanyStats(), loadCompanyProfile()]);
};

const handleAssign = (row: ProductKey) => {
  assignKeyId.value = row.id;
  assignForm.user_id = undefined;
  assignDialogVisible.value = true;
};

const confirmAssign = async () => {
  if (!assignFormRef.value || !assignForm.user_id) {
    return;
  }
  try {
    await assignFormRef.value.validate();
    const user = companyUsers.value.find((item) => item.id === assignForm.user_id);
    if (!user) {
      ElMessage.error(t('targetUserNotFound'));
      return;
    }
    await assignCompanyKey(assignKeyId.value, {
      user_id: user.id,
      user_name: user.name,
      operator: authStore.username || 'company_admin'
    });
    assignDialogVisible.value = false;
    ElMessage.success(t('assignSuccess'));
    await Promise.all([loadList(), loadCompanyStats(), loadCompanyProfile()]);
  } catch {
    ElMessage.error(t('assignFailed'));
  }
};

const handleRevoke = async (row: ProductKey) => {
  try {
    await revokeCompanyKey(row.id, authStore.username || 'company_admin');
    ElMessage.success(t('revokeSuccess'));
    await Promise.all([loadList(), loadCompanyStats(), loadCompanyProfile()]);
  } catch {
    ElMessage.error(t('revokeFailed'));
  }
};

const handleView = (row: ProductKey) => {
  selectedKey.value = row;
  detailDialogVisible.value = true;
};

onMounted(async () => {
  await Promise.all([loadCompanyUsers(), loadList(), loadCompanyStats(), loadCompanyProfile()]);
});
</script>

<style scoped>
.company-product-keys-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.page-header h1 {
  margin: 0;
  font-size: 24px;
}

.stats-cards {
  display: grid;
  grid-template-columns: repeat(5, minmax(120px, 1fr));
  gap: 12px;
}

.stat-value {
  font-size: 22px;
  font-weight: 700;
}

.stat-label {
  color: #64748b;
  font-size: 13px;
  margin-top: 8px;
}

.action-bar {
  display: flex;
  gap: 12px;
}

.pagination {
  display: flex;
  justify-content: flex-end;
}

.is-expired-time {
  color: #dc2626;
  font-weight: 600;
}

@media (max-width: 960px) {
  .stats-cards {
    grid-template-columns: repeat(2, minmax(120px, 1fr));
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
}
</style>
