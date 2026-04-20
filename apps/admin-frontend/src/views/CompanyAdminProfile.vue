<template>
  <div class="company-admin-profile">
    <el-card v-loading="loading" class="profile-card">
      <template #header>
        <div class="card-header">
          <h2>企业管理员信息</h2>
          <el-tag :type="profile?.company_admin_type === 'trial' ? 'warning' : 'success'">
            {{ profileTypeLabel }}
          </el-tag>
        </div>
      </template>

      <el-empty v-if="!profile && !loading" description="暂无企业管理员信息" />

      <template v-else-if="profile">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="企业名称">{{ profile.company_name }}</el-descriptions-item>
          <el-descriptions-item label="企业ID">{{ profile.company_id }}</el-descriptions-item>
          <el-descriptions-item label="管理员类型">{{ profileTypeLabel }}</el-descriptions-item>
          <el-descriptions-item label="已创建密钥数量">{{ profile.total_keys_created }}</el-descriptions-item>
          <el-descriptions-item label="最大可创建数量">{{ profile.max_keys_allowed }}</el-descriptions-item>
          <el-descriptions-item label="剩余可创建数量">{{ profile.remaining_keys_quota }}</el-descriptions-item>
          <el-descriptions-item label="允许创建的密钥类型" :span="2">
            <el-tag
              v-for="item in profile.allowed_key_types"
              :key="item"
              class="type-tag"
              type="info"
            >
              {{ keyTypeLabel(item) }}
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>

        <div class="quota-block">
          <div class="quota-title">角色配额使用进度</div>
          <el-progress
            :percentage="usagePercent"
            :status="usagePercent >= 100 ? 'exception' : usagePercent >= 80 ? 'warning' : 'success'"
            :stroke-width="16"
          />
          <div class="quota-text">{{ profile.total_keys_created }} / {{ profile.max_keys_allowed }}</div>
        </div>
      </template>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import type { CompanyAdmin } from '../types/admin';
import { computed, onMounted, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { useAuthStore } from '../stores/auth';
import { fetchCompanyAdminProfile } from '../services/http';

const authStore = useAuthStore();
const loading = ref(false);
const profile = ref<CompanyAdmin | null>(null);

const profileTypeLabel = computed(() => (profile.value?.company_admin_type === 'trial' ? '试用企业管理员' : '标准企业管理员'));
const usagePercent = computed(() => {
  if (!profile.value || profile.value.max_keys_allowed <= 0) {
    return 0;
  }
  return Math.min(100, Math.round((profile.value.total_keys_created / profile.value.max_keys_allowed) * 100));
});

const keyTypeLabel = (value: CompanyAdmin['allowed_key_types'][number]) =>
  value === 'enterprise_trial' ? '企业试用' : '企业标准';

const loadProfile = async () => {
  loading.value = true;
  try {
    profile.value = await fetchCompanyAdminProfile(authStore.currentCompany.id);
  } catch {
    ElMessage.error('加载企业管理员信息失败');
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  void loadProfile();
});
</script>

<style scoped>
.company-admin-profile {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.profile-card {
  border-radius: 12px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-header h2 {
  margin: 0;
  font-size: 20px;
}

.type-tag {
  margin-right: 8px;
}

.quota-block {
  margin-top: 20px;
}

.quota-title {
  margin-bottom: 8px;
  font-size: 14px;
  color: #334155;
}

.quota-text {
  margin-top: 8px;
  color: #475569;
  font-size: 13px;
}
</style>
