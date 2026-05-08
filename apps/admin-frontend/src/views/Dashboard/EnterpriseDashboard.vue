<template>
  <div class="enterprise-dashboard">
    <el-card class="hero-card">
      <h2>企业工作台</h2>
      <p>当前账号角色：{{ roleLabel }}</p>
      <p v-if="email">登录邮箱：{{ email }}</p>
    </el-card>

    <section class="quick-actions">
      <el-card class="action-card" @click="router.push('/enterprise-management')">
        <h3>企业管理</h3>
        <p>查看企业级配置与状态</p>
      </el-card>
      <el-card class="action-card" @click="router.push('/company/product-keys')" v-if="role === 'company_admin'">
        <h3>企业密钥</h3>
        <p>管理企业可用密钥与配额</p>
      </el-card>
      <el-card class="action-card" @click="router.push('/tickets')">
        <h3>工单中心</h3>
        <p>处理企业运营支持工单</p>
      </el-card>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '../../stores/auth';

const router = useRouter();
const authStore = useAuthStore();

const role = computed(() => authStore.user?.role ?? '');
const email = computed(() => authStore.user?.email ?? '');
const roleLabel = computed(() => {
  if (role.value === 'enterprise') {
    return 'enterprise';
  }
  if (role.value === 'company_admin') {
    return 'company_admin';
  }
  return role.value || '-';
});
</script>

<style scoped>
.enterprise-dashboard { display: flex; flex-direction: column; gap: 12px; }
.hero-card h2 { margin: 0 0 8px 0; }
.hero-card p { margin: 0; color: #475569; }
.quick-actions { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.action-card { cursor: pointer; }
.action-card h3 { margin: 0 0 8px 0; }
.action-card p { margin: 0; color: #64748b; }
@media (max-width: 1080px) { .quick-actions { grid-template-columns: 1fr; } }
</style>
