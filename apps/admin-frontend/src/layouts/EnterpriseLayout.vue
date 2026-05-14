<template>
  <div class="enterprise-layout">
    <aside class="sidebar">
      <div class="brand">{{ t('appTitle_enterprise') }}</div>
      <el-menu
        :default-active="activePath"
        class="menu"
        router
      >
        <el-menu-item index="/enterprise/dashboard">
          <el-icon><Histogram /></el-icon>
          <span>{{ t('dashboard') }}</span>
        </el-menu-item>
        <el-menu-item index="/enterprise/management">
          <el-icon><UserFilled /></el-icon>
          <span>{{ t('companymanage') }}</span>
        </el-menu-item>
        <el-menu-item index="/enterprise/workflows">
          <el-icon><Operation /></el-icon>
          <span>{{ t('workflowEngine') }}</span>
        </el-menu-item>
        <el-menu-item index="/enterprise/users">
          <el-icon><UserFilled /></el-icon>
          <span>{{ t('users') }}</span>
        </el-menu-item>
        <el-menu-item index="/enterprise/tickets">
          <el-icon><Document /></el-icon>
          <span>{{ t('tickets') }}</span>
        </el-menu-item>
      </el-menu>
    </aside>

    <section class="content-wrap">
      <header class="topbar">
        <div class="title-wrap">
          <div class="title">{{ currentTitle }}</div>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item
              v-for="item in breadcrumbs"
              :key="item.path"
              :to="item.clickable ? item.path : undefined"
            >
              {{ item.label }}
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="actions">
          <el-select :model-value="appStore.language" style="width: 120px" @change="onLanguageChange">
            <el-option label="简体中文" value="zh-CN" />
            <el-option label="English" value="en-US" />
            <el-option label="日本語" value="ja-JP"/>
            <el-option label="繁體中文" value="zh-TW"/>
            <el-option label="한국어" value="ko-KR"/>
          </el-select>
          <span class="user">{{ authStore.user_Name }}</span>
          <el-button type="danger" plain @click="onLogout">{{ t('logout') }}</el-button>
        </div>
      </header>
      <main class="content">
        <router-view v-slot="{ Component, route: currentRoute }">
          <transition name="fade-transform" mode="out-in">
            <component :is="Component" :key="currentRoute.path" />
          </transition>
        </router-view>
      </main>
    </section>
  </div>
</template>

<script setup lang="ts">
import type { AppLanguage } from '../stores/app';
import { computed } from 'vue';
import { ElMessage } from 'element-plus';
import { Document, Histogram, Operation, UserFilled } from '@element-plus/icons-vue';
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

const currentTitle = computed(() => {
  const titleKey = typeof route.meta.titleKey === 'string' ? route.meta.titleKey : '';
  if (titleKey) {
    return t(titleKey);
  }
  const title = typeof route.meta.title === 'string' ? route.meta.title : '';
  return title || t('appTitle_enterprise');
});

const breadcrumbs = computed(() => {
  return route.matched
    .filter((record) => Boolean(record.path) && !record.path.includes(':'))
    .map((record, index, arr) => {
      const key =
        typeof record.meta.breadcrumbKey === 'string'
          ? record.meta.breadcrumbKey
          : typeof record.meta.titleKey === 'string'
            ? record.meta.titleKey
            : '';
      const label = key ? t(key) : String(record.meta.title || t('appTitle_enterprise'));
      return {
        path: record.path,
        label,
        clickable: index < arr.length - 1
      };
    })
    .filter((item) => item.path !== '/');
});

const onLanguageChange = (language: AppLanguage) => {
  appStore.setLanguage(language);
};

const onLogout = () => {
  authStore.logout();
  ElMessage.success(t('logoutsuccess'));
  router.push('/login/enterprise');
};
</script>

<style scoped>
.enterprise-layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  height: 100vh;
  background: #f8fafc;
}

.sidebar {
  background: #0f172a;
  color: #fff;
  padding: 18px 12px;
}

.brand {
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 24px;
  padding: 0 12px;
  color: #10b981;
}

.menu {
  border-right: none;
  background: transparent;
}

.menu :deep(.el-menu-item) {
  color: #94a3b8;
  border-radius: 8px;
  margin-bottom: 4px;
}

.menu :deep(.el-menu-item:hover) {
  color: #fff;
  background: #1e293b;
}

.menu :deep(.el-menu-item.is-active) {
  color: #fff;
  background: #10b981;
}

.content-wrap {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.topbar {
  height: 64px;
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e2e8f0;
  background: #fff;
}

.title-wrap {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.title {
  font-size: 18px;
  font-weight: 600;
  color: #1e293b;
}

.actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.user {
  color: #64748b;
  font-weight: 500;
}

.content {
  flex: 1;
  padding: 24px;
  overflow: auto;
}

.fade-transform-enter-active,
.fade-transform-leave-active {
  transition: all 0.2s;
}

.fade-transform-enter-from {
  opacity: 0;
  transform: translateX(-10px);
}

.fade-transform-leave-to {
  opacity: 0;
  transform: translateX(10px);
}
</style>
