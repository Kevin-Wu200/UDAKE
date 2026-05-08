<template>
  <div class="dashboard-entry">
    <el-segmented
      v-if="isCompanyAdmin"
      v-model="activeView"
      :options="viewOptions"
      class="view-switch"
    />
    <component :is="currentView" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useAuthStore } from '../stores/auth';
import AdminDashboard from './Dashboard/AdminDashboard.vue';
import EnterpriseDashboard from './Dashboard/EnterpriseDashboard.vue';

const authStore = useAuthStore();
const role = computed(() => authStore.user?.role ?? '');
const isCompanyAdmin = computed(() => role.value === 'company_admin');

const activeView = ref<'admin' | 'enterprise'>('admin');
const viewOptions = [
  { label: '管理视角', value: 'admin' },
  { label: '企业视角', value: 'enterprise' }
];

const currentView = computed(() => {
  if (role.value === 'enterprise') {
    return EnterpriseDashboard;
  }
  if (isCompanyAdmin.value && activeView.value === 'enterprise') {
    return EnterpriseDashboard;
  }
  return AdminDashboard;
});
</script>

<style scoped>
.dashboard-entry { display: flex; flex-direction: column; gap: 12px; }
.view-switch { width: fit-content; }
</style>
