<template>
  <div class="page-card">
    <div class="toolbar">
      <el-select v-model="filters.role" clearable placeholder="角色" style="width: 140px">
        <el-option label="管理员" value="admin" />
        <el-option label="审计员" value="auditor" />
        <el-option label="访客" value="viewer" />
      </el-select>
      <el-select v-model="filters.status" clearable placeholder="状态" style="width: 140px">
        <el-option label="启用" value="enabled" />
        <el-option label="禁用" value="disabled" />
      </el-select>
      <el-input v-model="filters.keyword" clearable style="width: 260px" placeholder="搜索用户名/邮箱" />
      <el-button type="primary" @click="search">查询</el-button>
      <el-button @click="resetSearch">重置</el-button>
    </div>

    <el-table :data="list" border>
      <el-table-column prop="username" label="用户名" min-width="140" />
      <el-table-column prop="email" label="邮箱" min-width="200" />
      <el-table-column prop="role" label="角色" width="120">
        <template #default="scope">{{ roleText(scope.row.role) }}</template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="120">
        <template #default="scope">
          <el-switch
            :model-value="scope.row.status"
            inline-prompt
            active-text="启用"
            inactive-text="禁用"
            @change="(value) => onStatusChange(scope.row, Boolean(value))"
          />
        </template>
      </el-table-column>
      <el-table-column prop="createdAt" label="创建时间" width="170" />
      <el-table-column prop="lastLoginAt" label="最后登录时间" width="170" />
      <el-table-column label="操作" width="210" fixed="right">
        <template #default="scope">
          <el-button size="small" @click="openDrawer(scope.row)">详情</el-button>
          <el-button size="small" type="warning" @click="onResetPassword(scope.row)">重置密码</el-button>
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

  <el-drawer v-model="drawerVisible" title="用户详情" size="42%">
    <template v-if="selectedUser">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="用户名">{{ selectedUser.username }}</el-descriptions-item>
        <el-descriptions-item label="邮箱">{{ selectedUser.email }}</el-descriptions-item>
        <el-descriptions-item label="角色">{{ roleText(selectedUser.role) }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          {{ selectedUser.status ? '启用' : '禁用' }}
        </el-descriptions-item>
      </el-descriptions>

      <h4 class="drawer-title">设备列表</h4>
      <el-table :data="selectedUser.devices" size="small" border>
        <el-table-column prop="name" label="设备" />
        <el-table-column prop="os" label="系统" width="120" />
        <el-table-column prop="lastActiveAt" label="最近活跃" width="170" />
      </el-table>

      <h4 class="drawer-title">登录日志</h4>
      <el-table :data="selectedUser.loginLogs" size="small" border>
        <el-table-column prop="time" label="时间" width="170" />
        <el-table-column prop="ip" label="IP" width="160" />
        <el-table-column prop="result" label="结果">
          <template #default="scope">
            <el-tag :type="scope.row.result === 'success' ? 'success' : 'danger'">
              {{ scope.row.result === 'success' ? '成功' : '失败' }}
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
import { fetchUsers, resetUserPassword, updateUserStatus } from '../services/mockApi';

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

const roleText = (role: UserRole) => {
  const map: Record<UserRole, string> = {
    admin: '管理员',
    auditor: '审计员',
    viewer: '访客'
  };
  return map[role];
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
    ElMessage.error('获取用户列表失败');
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
    await ElMessageBox.confirm(`确认重置 ${user.username} 的密码吗？`, '重置密码', {
      type: 'warning',
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      modalClass: 'admin-confirm-dialog-overlay',
      closeOnClickModal: false,
      closeOnPressEscape: false
    });
    await resetUserPassword(user.id);
    ElMessage.success('密码重置邮件已发送');
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      console.error('重置密码失败:', error);
      ElMessage.error('操作失败，请重试');
    }
  }
};

const onStatusChange = async (user: UserItem, enabled: boolean) => {
  const previous = user.status;
  user.status = enabled;
  try {
    await updateUserStatus(user.id, enabled);
    ElMessage.success(enabled ? '用户已启用' : '用户已禁用');
  } catch {
    user.status = previous;
    ElMessage.error('更新状态失败');
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
</style>
