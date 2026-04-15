<template>
  <div class="product-keys-view">
    <div class="page-header">
      <h1>产品密钥管理</h1>
      <div class="stats-cards">
        <el-card class="stat-card">
          <div class="stat-value">{{ stats.total }}</div>
          <div class="stat-label">总密钥数</div>
        </el-card>
        <el-card class="stat-card">
          <div class="stat-value">{{ stats.active }}</div>
          <div class="stat-label">活跃密钥</div>
        </el-card>
        <el-card class="stat-card">
          <div class="stat-value">{{ stats.unused }}</div>
          <div class="stat-label">未使用</div>
        </el-card>
      </div>
    </div>

    <el-card class="filter-card">
      <el-form :inline="true" :model="filterForm">
        <el-form-item label="密钥类型">
          <el-select v-model="filterForm.type" placeholder="选择类型" clearable style="width: 180px">
            <el-option label="个人试用" value="personal_trial" />
            <el-option label="个人标准" value="personal_standard" />
            <el-option label="企业试用" value="enterprise_trial" />
            <el-option label="企业标准" value="enterprise_standard" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filterForm.status" placeholder="选择状态" clearable style="width: 160px">
            <el-option label="未使用" value="unused" />
            <el-option label="活跃" value="active" />
            <el-option label="已禁用" value="disabled" />
            <el-option label="已过期" value="expired" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键字">
          <el-input
            v-model="filterForm.keyword"
            placeholder="密钥/企业/用户ID"
            clearable
            style="width: 240px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">搜索</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <div class="action-bar">
      <el-button type="primary" @click="createDialogVisible = true" :disabled="!canCreate || createDisabledByQuota">
        创建单个密钥
      </el-button>
      <el-button @click="importDialogVisible = true" :disabled="!canImport">批量导入</el-button>
    </div>

    <el-alert
      v-if="companyAdminProfile"
      :type="createDisabledByQuota ? 'error' : 'info'"
      :closable="false"
      show-icon
      class="quota-alert"
      :title="`当前角色：${companyAdminTypeLabel}，可创建类型：${allowedTypeLabels}，配额：${companyAdminProfile.total_keys_created}/${companyAdminProfile.max_keys_allowed}`"
      :description="createDisabledByQuota ? '已达到创建上限，无法继续创建密钥。' : `剩余可创建 ${companyAdminProfile.remaining_keys_quota} 个。`"
    />

    <el-table :data="keys" border v-loading="loading">
      <el-table-column prop="product_key" label="密钥" min-width="220" />
      <el-table-column prop="key_type" label="类型" width="130">
        <template #default="{ row }">
          {{ getKeyTypeLabel(row.key_type) }}
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="getStatusType(row.status)">{{ getStatusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="total_quota" label="总配额" width="100" />
      <el-table-column prop="used_count" label="已使用" width="100" />
      <el-table-column prop="company_id" label="企业ID" width="100">
        <template #default="{ row }">
          {{ row.company_id || '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="user_id" label="用户ID" width="100">
        <template #default="{ row }">
          {{ row.user_id || '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="expires_at" label="过期时间" width="180">
        <template #default="{ row }">
          <div class="expires-cell">
            <el-icon v-if="isExpired(row)" class="expired-icon"><WarningFilled /></el-icon>
            <span :class="{ 'expired-text': isExpired(row) }">{{ row.expires_at || '-' }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="到期倒计时" width="140">
        <template #default="{ row }">
          <el-tag :type="countdownTagType(row)">
            {{ getCountdownText(row) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="assigned_at" label="分配时间" width="170" />
      <el-table-column prop="created_at" label="创建时间" width="170" />
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="handleView(row)">查看</el-button>
          <el-button link type="primary" @click="handleEdit(row)" :disabled="!canEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="handleDelete(row)" :disabled="!canDelete(row)">删除</el-button>
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

    <el-dialog v-model="createDialogVisible" title="创建单个密钥" width="460px">
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="110px">
        <el-form-item label="密钥类型" prop="type">
          <el-select v-model="createForm.type" style="width: 100%">
            <el-option
              v-for="item in creatableTypeOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="企业ID" prop="company_id">
          <el-input-number v-model="createForm.company_id" :min="1" :max="999999" style="width: 100%" />
        </el-form-item>
        <el-form-item label="用户ID" prop="user_id">
          <el-input-number v-model="createForm.user_id" :min="1" :max="999999" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备注" prop="notes">
          <el-input v-model="createForm.notes" type="textarea" :rows="3" maxlength="120" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCreateSingle" :disabled="createDisabledByQuota">确认创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="importDialogVisible" title="批量导入密钥" width="560px">
      <el-alert
        type="info"
        :closable="false"
        title="每行格式：product_key,key_type,status,company_id,enterprise_name"
      />
      <el-input
        v-model="importText"
        type="textarea"
        :rows="9"
        style="margin-top: 12px"
        placeholder="示例: ABC-1234-5678-9XYZ,enterprise_standard,unused,12,企业A"
      />
      <div v-if="importResult" class="import-result">
        <el-tag type="success">成功 {{ importResult.successCount }}</el-tag>
        <el-tag type="danger">失败 {{ importResult.failedCount }}</el-tag>
        <el-text v-if="importResult.failedLines.length" type="danger">
          失败行：{{ importResult.failedLines.join(' | ') }}
        </el-text>
      </div>
      <template #footer>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleImport">解析并导入</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editDialogVisible" title="编辑密钥" width="460px">
      <el-form ref="editFormRef" :model="editForm" :rules="editRules" label-width="100px">
        <el-form-item label="状态" prop="status">
          <el-select v-model="editForm.status" style="width: 100%">
            <el-option label="未使用" value="unused" />
            <el-option label="活跃" value="active" />
            <el-option label="已禁用" value="disabled" />
            <el-option label="已过期" value="expired" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注" prop="notes">
          <el-input v-model="editForm.notes" type="textarea" :rows="3" maxlength="120" show-word-limit />
        </el-form-item>
        <el-form-item label="延长天数" prop="extend_days">
          <el-input-number
            v-model="editForm.extend_days"
            :min="0"
            :max="3650"
            :step="30"
            controls-position="right"
            style="width: 100%"
          />
          <div class="form-tip">为0表示取消过期限制，默认30天为步长</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleUpdate">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="detailDialogVisible" title="密钥详情" width="640px">
      <el-descriptions :column="2" border v-if="detailKey">
        <el-descriptions-item label="密钥">{{ detailKey.product_key }}</el-descriptions-item>
        <el-descriptions-item label="类型">{{ getKeyTypeLabel(detailKey.key_type) }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ getStatusLabel(detailKey.status) }}</el-descriptions-item>
        <el-descriptions-item label="总配额">{{ detailKey.total_quota }}</el-descriptions-item>
        <el-descriptions-item label="已使用">{{ detailKey.used_count }}</el-descriptions-item>
        <el-descriptions-item label="企业ID">{{ detailKey.company_id || '-' }}</el-descriptions-item>
        <el-descriptions-item label="用户ID">{{ detailKey.user_id || '-' }}</el-descriptions-item>
        <el-descriptions-item label="分配时间">{{ detailKey.assigned_at || '-' }}</el-descriptions-item>
        <el-descriptions-item label="企业名">{{ detailKey.metadata?.enterprise_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="备注">{{ detailKey.metadata?.notes || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import type { FormInstance, FormRules } from 'element-plus';
import type { CompanyAdmin, KeyStatus, KeyType, ProductKey } from '../types/admin';
import { computed, onMounted, reactive, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { WarningFilled } from '@element-plus/icons-vue';
import { useAuthStore } from '../stores/auth';
import {
  createProductKeys,
  deleteProductKey,
  fetchCompanyAdminProfile,
  fetchProductKeyStats,
  fetchProductKeys,
  importProductKeys,
  updateProductKey
} from '../services/mockApi';

const authStore = useAuthStore();
const loading = ref(false);
const keys = ref<ProductKey[]>([]);
const detailKey = ref<ProductKey | null>(null);

const filterForm = reactive<{
  type?: KeyType;
  status?: KeyStatus;
  keyword: string;
}>({
  type: undefined,
  status: undefined,
  keyword: ''
});

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
});

const stats = reactive({
  total: 0,
  active: 0,
  unused: 0
});

const isSuperAdmin = computed(() => authStore.isSuperAdmin || authStore.user?.role === 'admin');
const canCreate = computed(() => isSuperAdmin.value);
const canImport = computed(() => isSuperAdmin.value);
const canEdit = (key: ProductKey) => isSuperAdmin.value && key.status !== 'expired';
const canDelete = (key: ProductKey) => isSuperAdmin.value && key.status === 'unused';
const companyAdminProfile = ref<CompanyAdmin | null>(null);

const companyAdminTypeLabel = computed(() =>
  companyAdminProfile.value?.company_admin_type === 'trial' ? '试用企业管理员' : '标准企业管理员'
);

const creatableTypeOptions = computed<Array<{ label: string; value: KeyType }>>(() => {
  if (!companyAdminProfile.value) {
    return [
      { label: '个人试用', value: 'personal_trial' },
      { label: '个人标准', value: 'personal_standard' },
      { label: '企业试用', value: 'enterprise_trial' },
      { label: '企业标准', value: 'enterprise_standard' }
    ];
  }
  return companyAdminProfile.value.allowed_key_types.map((value) => ({
    value,
    label: value === 'enterprise_trial' ? '企业试用' : '企业标准'
  }));
});

const allowedTypeLabels = computed(() => creatableTypeOptions.value.map((item) => item.label).join('、'));
const createDisabledByQuota = computed(() =>
  Boolean(companyAdminProfile.value && companyAdminProfile.value.remaining_keys_quota <= 0)
);

const createDialogVisible = ref(false);
const importDialogVisible = ref(false);
const editDialogVisible = ref(false);
const detailDialogVisible = ref(false);

const createFormRef = ref<FormInstance>();
const editFormRef = ref<FormInstance>();

const createForm = reactive({
  type: 'personal_standard' as KeyType,
  company_id: undefined as number | undefined,
  user_id: undefined as number | undefined,
  notes: ''
});

const editForm = reactive({
  id: 0,
  status: 'unused' as KeyStatus,
  notes: '',
  extend_days: undefined as number | undefined
});

const importText = ref('');
const importResult = ref<{
  successCount: number;
  failedCount: number;
  failedLines: string[];
} | null>(null);

const createRules: FormRules<typeof createForm> = {
  type: [{ required: true, message: '请选择密钥类型', trigger: 'change' }],
  company_id: [
    {
      validator: (_rule, value, callback) => {
        if (createForm.type.startsWith('enterprise') && !value) {
          callback(new Error('企业类型密钥必须指定企业ID'));
          return;
        }
        callback();
      },
      trigger: 'change'
    }
  ]
};

const editRules: FormRules<typeof editForm> = {
  status: [{ required: true, message: '请选择状态', trigger: 'change' }],
  extend_days: [{ type: 'number', min: 0, max: 3650, message: '延长天数范围 0-3650' }]
};

const getKeyTypeLabel = (type: KeyType) => {
  const map: Record<KeyType, string> = {
    personal_trial: '个人试用',
    personal_standard: '个人标准',
    enterprise_trial: '企业试用',
    enterprise_standard: '企业标准'
  };
  return map[type];
};

const getStatusLabel = (status: KeyStatus) => {
  const map: Record<KeyStatus, string> = {
    unused: '未使用',
    active: '活跃',
    disabled: '已禁用',
    expired: '已过期'
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

const loadStats = async () => {
  const res = await fetchProductKeyStats();
  stats.total = res.total;
  stats.active = res.active;
  stats.unused = res.unused;
};

const loadList = async () => {
  loading.value = true;
  try {
    const res = await fetchProductKeys({
      page: pagination.page,
      pageSize: pagination.pageSize,
      type: filterForm.type,
      status: filterForm.status,
      keyword: filterForm.keyword
    });
    keys.value = res.items;
    pagination.total = res.total;
  } catch {
    ElMessage.error('获取密钥列表失败');
  } finally {
    loading.value = false;
  }
};

const handleSearch = async () => {
  pagination.page = 1;
  await loadList();
};

const handleReset = async () => {
  filterForm.type = undefined;
  filterForm.status = undefined;
  filterForm.keyword = '';
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

const resetCreateForm = () => {
  createForm.type = creatableTypeOptions.value[0]?.value ?? 'personal_standard';
  createForm.company_id = undefined;
  createForm.user_id = undefined;
  createForm.notes = '';
};

const handleCreateSingle = async () => {
  if (!createFormRef.value) {
    return;
  }
  try {
    await createFormRef.value.validate();
    await createProductKeys({
      type: createForm.type,
      count: 1,
      company_id: createForm.company_id,
      user_id: createForm.user_id,
      metadata: {
        notes: createForm.notes,
        enterprise_name: createForm.company_id ? `企业${createForm.company_id}` : undefined
      }
    });
    createDialogVisible.value = false;
    resetCreateForm();
    ElMessage.success('创建成功');
    await Promise.all([loadList(), loadStats(), loadCompanyAdminProfile()]);
  } catch {
    ElMessage.error('创建失败');
  }
};

const handleImport = async () => {
  if (!importText.value.trim()) {
    ElMessage.warning('请输入导入内容');
    return;
  }
  try {
    importResult.value = await importProductKeys(importText.value);
    ElMessage.success('导入已完成');
    await Promise.all([loadList(), loadStats()]);
  } catch {
    ElMessage.error('导入失败');
  }
};

const handleView = (row: ProductKey) => {
  detailKey.value = row;
  detailDialogVisible.value = true;
};

const handleEdit = (row: ProductKey) => {
  editForm.id = row.id;
  editForm.status = row.status;
  editForm.notes = row.metadata?.notes || '';
  editForm.extend_days = undefined;
  editDialogVisible.value = true;
};

const handleUpdate = async () => {
  if (!editFormRef.value) {
    return;
  }

  try {
    await editFormRef.value.validate();
    await updateProductKey(editForm.id, {
      status: editForm.status,
      notes: editForm.notes,
      extend_days: editForm.extend_days
    });
    editDialogVisible.value = false;
    ElMessage.success('更新成功');
    await Promise.all([loadList(), loadStats()]);
  } catch {
    ElMessage.error('更新失败');
  }
};

const handleDelete = async (row: ProductKey) => {
  try {
    await ElMessageBox.confirm(`确认删除密钥 ${row.product_key} 吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    });
    await deleteProductKey(row.id);
    ElMessage.success('删除成功');
    if (keys.value.length === 1 && pagination.page > 1) {
      pagination.page -= 1;
    }
    await Promise.all([loadList(), loadStats()]);
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error('操作失败，请重试');
    }
  }
};

const toTimestamp = (value?: string) => {
  if (!value) {
    return Number.NaN;
  }
  const normalized = value.replace(' ', 'T');
  const ts = new Date(normalized).getTime();
  return Number.isNaN(ts) ? Number.NaN : ts;
};

const isExpired = (key: ProductKey) => key.status === 'expired' || (!Number.isNaN(toTimestamp(key.expires_at)) && toTimestamp(key.expires_at) <= Date.now());

const getCountdownText = (key: ProductKey) => {
  if (!key.expires_at) {
    return '未设置';
  }
  const expiry = toTimestamp(key.expires_at);
  if (Number.isNaN(expiry)) {
    return '时间异常';
  }
  const remainMs = expiry - Date.now();
  const dayMs = 24 * 60 * 60 * 1000;
  if (remainMs <= 0) {
    return '已到期';
  }
  const days = Math.ceil(remainMs / dayMs);
  return `剩余 ${days} 天`;
};

const countdownTagType = (key: ProductKey): 'info' | 'danger' | 'warning' | 'success' => {
  const text = getCountdownText(key);
  if (text === '已到期') {
    return 'danger';
  }
  const match = text.match(/\d+/);
  const days = match ? Number(match[0]) : 999;
  if (days <= 7) {
    return 'warning';
  }
  return 'success';
};

const loadCompanyAdminProfile = async () => {
  if (!authStore.isCompanyAdmin) {
    companyAdminProfile.value = null;
    return;
  }
  try {
    const profile = await fetchCompanyAdminProfile(authStore.currentCompany.id);
    companyAdminProfile.value = profile;
    if (!profile.allowed_key_types.includes(createForm.type as 'enterprise_trial' | 'enterprise_standard')) {
      createForm.type = profile.allowed_key_types[0] ?? 'enterprise_trial';
    }
  } catch {
    companyAdminProfile.value = null;
  }
};

onMounted(async () => {
  await Promise.all([loadList(), loadStats(), loadCompanyAdminProfile()]);
});
</script>

<style scoped>
.product-keys-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.page-header h1 {
  margin: 0;
  font-size: 24px;
}

.stats-cards {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.stat-card {
  width: 120px;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  line-height: 1;
}

.stat-label {
  margin-top: 8px;
  color: #64748b;
  font-size: 13px;
}

.filter-card {
  border-radius: 10px;
}

.action-bar {
  display: flex;
  gap: 12px;
}

.quota-alert {
  margin-top: 4px;
}

.expires-cell {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.expired-icon {
  color: #ef4444;
}

.expired-text {
  color: #dc2626;
  font-weight: 600;
}

.pagination {
  display: flex;
  justify-content: flex-end;
}

.import-result {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-tip {
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
}

@media (max-width: 900px) {
  .page-header {
    flex-direction: column;
  }
}
</style>
