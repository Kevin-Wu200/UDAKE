<template>
  <div class="admin-layout">
    <aside class="sidebar">
      <div class="brand">{{ t('appTitle') }}</div>
      <el-menu
        :default-active="activePath"
        class="menu"
        router
      >
        <el-menu-item index="/dashboard">{{ t('dashboard') }}</el-menu-item>
        <el-menu-item index="/product-keys">{{ t('productKeys') }}</el-menu-item>
        <el-menu-item index="/workflows">{{ t('workflowEngine') }}</el-menu-item>
        <el-menu-item index="/users">{{ t('users') }}</el-menu-item>
        <el-menu-item index="/audit-logs">{{ t('auditLogs') }}</el-menu-item>
      </el-menu>
    </aside>

    <section class="content-wrap">
      <header class="topbar">
        <div class="title">{{ route.meta.title || t('appTitle') }}</div>
        <div class="actions">
          <el-select :model-value="appStore.language" style="width: 120px" @change="onLanguageChange">
            <el-option label="中文" value="zh-CN" />
            <el-option label="English" value="en-US" />
          </el-select>
          <span class="user">{{ authStore.username }}</span>
          <el-button type="danger" plain @click="onLogout">{{ t('logout') }}</el-button>
        </div>
      </header>
      <main class="content">
        <router-view />
      </main>
    </section>
  </div>
</template>

<script setup lang="ts">
import type { AppLanguage } from '../stores/app';
import { computed } from 'vue';
import { ElMessage } from 'element-plus';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '../stores/auth';
import { useAppStore } from '../stores/app';
import { useI18nText } from '../i18n/useI18n';

const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();
const appStore = useAppStore();
const { t } = useI18nText();

const activePath = computed(() => route.path);

const onLanguageChange = (language: AppLanguage) => {
  appStore.setLanguage(language);
};

const onLogout = () => {
  authStore.logout();
  ElMessage.success('已退出登录');
  router.push('/login');
};
</script>

<style scoped>
.admin-layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  height: 100vh;
  background: linear-gradient(180deg, #f6fbff 0%, #f2f5fb 100%);
}

.sidebar {
  background: #102a43;
  color: #fff;
  padding: 18px 12px;
}

.brand {
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 16px;
  padding: 0 12px;
}

.menu {
  border-right: none;
  background: transparent;
}

.menu :deep(.el-menu-item) {
  color: #dbe8f4;
  border-radius: 8px;
  margin-bottom: 8px;
}

.menu :deep(.el-menu-item.is-active) {
  color: #102a43;
  background: #e7f0ff;
}

.content-wrap {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.topbar {
  height: 64px;
  padding: 0 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #dde6ef;
  background: #fff;
}

.title {
  font-size: 18px;
  font-weight: 600;
  color: #0f172a;
}

.actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user {
  color: #334155;
  font-weight: 500;
}

.content {
  flex: 1;
  padding: 20px;
  overflow: auto;
}

@media (max-width: 960px) {
  .admin-layout {
    grid-template-columns: 1fr;
  }

  .sidebar {
    padding: 10px;
  }

  .menu {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .menu :deep(.el-menu-item) {
    margin-bottom: 0;
  }
}
</style>
