<template>
  <div class="page-card">
    <div class="toolbar">
      <el-select v-model="filters.role" clearable :placeholder="t('role')" style="width: 140px">
        <el-option :label="t('admin')" value="admin" />
        <el-option :label="t('auditor')" value="auditor" />
        <el-option :label="t('user')" value="viewer" />
        <el-option :label="t('superadmin')" value="super_admin" />
        <el-option :label="t('companyadmin')" value="company_admin" />
        <el-option :label="t('enterprise')" value="enterprise" />
      </el-select>
      <el-select v-model="filters.status" clearable :placeholder="t('status')" style="width: 140px">
        <el-option :label="t('enable')" value="enabled" />
        <el-option :label="t('prohibit')" value="disabled" />
      </el-select>
      <el-input v-model="filters.keyword" clearable style="width: 260px" :placeholder="t('searchuser')" />
      <el-button type="primary" @click="search">{{ t('query') }}</el-button>
      <el-button @click="resetSearch">{{ t('reset') }}</el-button>
    </div>

    <el-table :data="list" border>
      <el-table-column prop="username" :label="t('username')" min-width="140" />
      <el-table-column prop="email" :label="t('email')" min-width="200" />
      <el-table-column prop="role" :label="t('role')" width="120">
        <template #default="scope">{{ roleText(scope.row.role) }}</template>
      </el-table-column>
      <el-table-column prop="status" :label="t('status')" width="120">
        <template #default="scope">
          <el-switch
            :model-value="scope.row.status"
            inline-prompt
            :active-text="t('on')"
            :inactive-text="t('off')"
            @change="(value) => onStatusChange(scope.row, Boolean(value))"
          />
        </template>
      </el-table-column>
      <el-table-column prop="createdAt" :label="t('createdat')" width="170" />
      <el-table-column prop="lastLoginAt" :label="t('finallogintime')" width="170" />
      <el-table-column :label="t('actions')" width="210" fixed="right">
        <template #default="scope">
          <div class="btn-group">
            <el-button size="small" @click="openDrawer(scope.row)">{{ t('details') }}</el-button>
            <el-button size="small" type="warning" @click="onResetPassword(scope.row)">{{ t('resetpw') }}</el-button>
          </div>
        </template>
      </el-table-column>
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

  <el-drawer v-model="drawerVisible" :title="t('userdetail')" size="42%">
    <template v-if="selectedUser">
      <el-descriptions :column="1" border>
        <el-descriptions-item :label="t('username')">{{ selectedUser.username }}</el-descriptions-item>
        <el-descriptions-item :label="t('email')">{{ selectedUser.email }}</el-descriptions-item>
        <el-descriptions-item :label="t('role')">{{ roleText(selectedUser.role) }}</el-descriptions-item>
        <el-descriptions-item :label="t('status')">
          {{ selectedUser.status ? t('enable') : t('prohibit') }}
        </el-descriptions-item>
      </el-descriptions>

      <h4 class="drawer-title">{{ t('devicelist') }}</h4>
      <el-table :data="selectedUser.devices" size="small" border>
        <el-table-column prop="name" :label="t('device')" />
        <el-table-column prop="os" :label="t('system')" width="120" />
        <el-table-column prop="lastActiveAt" :label="t('recentactive')" width="170" />
      </el-table>

      <h4 class="drawer-title">{{ t('loginlog') }}</h4>
      <el-table :data="selectedUser.loginLogs" size="small" border>
        <el-table-column prop="time" :label="t('time')" width="170" />
        <el-table-column prop="ip" label="IP" width="160" />
        <el-table-column prop="result" :label="t('result')">
          <template #default="scope">
            <el-tag :type="scope.row.result === 'success' ? 'success' : 'danger'">
              {{ scope.row.result === 'success' ? t('success') : t('failed') }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
import type { UserItem, UserRole } from '../types/admin';
import { onMounted, reactive, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { fetchUsers, resetUserPassword, updateUserStatus } from '../services/http';
import { useI18nText } from '../i18n/useI18n';

const { t } = useI18nText();

const list = ref<UserItem[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(10);

const filters = reactive<{
  role?: UserRole;
  status?: 'enabled' | 'disabled';
  keyword: string;
}>({
  role: undefined,
  status: undefined,
  keyword: ''
});

const drawerVisible = ref(false);
const selectedUser = ref<UserItem | null>(null);

const roleText = (role: UserRole | string) => {
  const map: Record<string, string> = {
    admin: t('admin'),
    auditor: t('auditor'),
    viewer: t('viewer'),
    super_admin: t('superadmin'),
    company_admin: t('companyadmin'),
    user: t('user'),
    enterprise: t('enterprise')
  };
  return map[role] || role || '-';
};

const loadList = async () => {
  try {
    const res = await fetchUsers({
      page: page.value,
      pageSize: pageSize.value,
      role: filters.role,
      status: filters.status,
      keyword: filters.keyword
    });
    list.value = res.items;
    total.value = res.total;
  } catch {
    ElMessage.error(t('getuserlistfailed'));
  }
};

const search = () => {
  page.value = 1;
  loadList();
};

const resetSearch = () => {
  filters.role = undefined;
  filters.status = undefined;
  filters.keyword = '';
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

const openDrawer = (user: UserItem) => {
  selectedUser.value = user;
  drawerVisible.value = true;
};

const onResetPassword = async (user: UserItem) => {
  try {
    await ElMessageBox.confirm(`${t('resetconfirm')} ${user.username} ${t('someonepw')}`, t('confirmreset'), {
      type: 'warning',
      confirmButtonText: t('confirm'),
      cancelButtonText: t('cancel'),
      modalClass: 'admin-confirm-dialog-overlay',
      closeOnClickModal: false,
      closeOnPressEscape: false
    });
    await resetUserPassword(user.id);
    ElMessage.success(t('sendpwresetpost'));
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      console.error(t('resetpwfailed'), error);
      ElMessage.error(t('actionfailed'));
    }
  }
};

const onStatusChange = async (user: UserItem, enabled: boolean) => {
  const previous = user.status;
  user.status = enabled;
  try {
    await updateUserStatus(user.id, enabled);
    ElMessage.success(enabled ? t('enableuser') : t('prohibituser'));
  } catch {
    user.status = previous;
    ElMessage.error(t('refreshstatusfailed'));
  }
};

onMounted(() => {
  loadList();
});
</script>

<style scoped>
.drawer-title {
  margin: 18px 0 10px;
  color: #0f172a;
}

.btn-group {
  display: flex;
  flex-wrap: nowrap;
  gap: 8px;
}
</style>
