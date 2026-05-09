<template>
  <div class="user-layout">
    <aside class="menu-panel">
      <h2>用户中心</h2>
      <el-menu :default-active="route.path" router>
        <el-menu-item index="/user/devices">设备管理</el-menu-item>
        <el-menu-item index="/user/change-password">修改密码</el-menu-item>
        <el-menu-item index="/user/change-email">修改邮箱</el-menu-item>
      </el-menu>
    </aside>

    <section class="main-panel">
      <header class="topbar">
        <div>
          <div class="title">账户安全中心</div>
          <div class="desc">{{ authStore.user?.email || authStore.username }}</div>
        </div>
        <div class="header-text">
          <div class="greeting">{{ greeting }}</div>
          <div class="sub">{{ t('welcome') }}{{ authStore.user_Name }}</div>
        </div>
        <div class="actions">
          <el-button plain @click="router.push('/dashboard')">管理员后台</el-button>
          
          <el-button type="danger" @click="onLogout">退出登录</el-button>
        </div>        
      </header>
      <main>
        <router-view />
      </main>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '../stores/auth';
import {ref, onMounted, watch} from 'vue';
import { useAppStore } from '../stores/app';
import { useI18nText } from '../i18n/useI18n';

const { t } = useI18nText();
const appStore = useAppStore();
const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();
const greeting = ref('');

const onLogout = async () => {
  await authStore.logoutWithApi();
  ElMessage.success('已退出登录');
  router.replace('/user/login');
};

function updateGreeting() {
  const hour = new Date().getHours();
  if (hour > 5 && hour < 12) {
    greeting.value = t('goodMorning');
  } else if (hour < 18) {
    greeting.value = t('goodAfternoon');
  } else if (hour < 22) {
    greeting.value = t('goodEvening');
  } else {
    greeting.value = t('goodNight');
  }
}

onMounted(() => {
  updateGreeting();
});

watch(() => appStore.language, () => {
  updateGreeting();
});
</script>

<style scoped>
.greeting {
  font-size: 28px;
  font-weight: 600;
  line-height: 1.3;
  color: #1d1d1f;
  letter-spacing: -0.02em;
  margin-bottom: 0;
  animation: fadeUp 0.5s ease;
}

.sub{
  font-size: 15px;
  font-weight: 400;
  line-height: 1.5;
  color: #86868b;
  letter-spacing: -0.01em;
  animation: fadeUp 0.7s ease;
}

.user-layout {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 240px 1fr;
  background: linear-gradient(180deg, #eff6ff 0%, #f8fafc 100%);
}

.menu-panel {
  background: #0f172a;
  color: #fff;
  padding: 20px 14px;
}

.menu-panel h2 {
  margin-bottom: 16px;
  font-size: 22px;
}

.menu-panel :deep(.el-menu) {
  border-right: none;
  background: transparent;
}

.menu-panel :deep(.el-menu-item) {
  color: #cbd5e1;
  border-radius: 10px;
  margin-bottom: 8px;
}

.menu-panel :deep(.el-menu-item.is-active) {
  color: #0f172a;
  background: #e2e8f0;
}

.main-panel {
  display: flex;
  flex-direction: column;
}

.topbar {
  height: 74px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: #fff;
  border-bottom: 1px solid #dbeafe;
}

.title {
  font-size: 18px;
  font-weight: 600;
}

.desc {
  margin-top: 4px;
  color: #64748b;
}

.actions {
  display: flex;
  gap: 10px;
}

main {
  flex: 1;
  padding: 20px;
  overflow: auto;
}

@media (max-width: 900px) {
  .user-layout {
    grid-template-columns: 1fr;
  }

  .menu-panel {
    padding: 12px;
  }

  .topbar {
    height: auto;
    padding: 12px;
    gap: 10px;
    flex-wrap: wrap;
  }
}

.header-text{
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 24px 0;
}

@keyframes fadeUp {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
