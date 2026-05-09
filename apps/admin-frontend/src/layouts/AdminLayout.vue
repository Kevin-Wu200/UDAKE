<template>
  <div class="admin-layout">
    <aside class="sidebar">
      <div class="brand">{{ t('appTitle') }}</div>
      <el-menu
        :default-active="activePath"
        :default-openeds="defaultOpeneds"
        class="menu"
        router
      >
        <el-menu-item index="/dashboard">
          <el-icon><Histogram /></el-icon>
          <span>{{ t('dashboard') }}</span>
        </el-menu-item>
        <el-menu-item v-if="!authStore.isCompanyAdmin" index="/product-keys">
          <el-icon><Key /></el-icon>
          <span>{{ t('productKeys') }}</span>
        </el-menu-item>
        <el-menu-item v-else index="/company/product-keys">
          <el-icon><Key /></el-icon>
          <span>{{ t('companyProductKeys') }}</span>
        </el-menu-item>
        <el-menu-item v-if="authStore.isCompanyAdmin" index="/company/profile">
          <el-icon><UserFilled /></el-icon>
          <span>{{ t('companyProfile') }}</span>
        </el-menu-item>
        <el-menu-item v-if="!authStore.isCompanyAdmin" index="/smtp-settings">
          <el-icon><Setting /></el-icon>
          <span>{{ t('smtpconfig') }}</span>
        </el-menu-item>
        <el-menu-item v-if="!authStore.isCompanyAdmin" index="/email-logs">
          <el-icon><Message /></el-icon>
          <span>{{ t('emaillog') }}</span>
        </el-menu-item>
        <el-menu-item index="/workflows">
          <el-icon><Operation /></el-icon>
          <span>{{ t('workflowEngine') }}</span>
        </el-menu-item>
        <el-sub-menu index="/history-analysis">
          <template #title>
            <el-icon><DataAnalysis /></el-icon>
            <span>{{ t('historyAnalysis') }}</span>
          </template>
          <el-menu-item index="/history-analysis/snapshots">{{ t('historyAnalysisSnapshots') }}</el-menu-item>
          <el-menu-item index="/history-analysis/compare">{{ t('historyAnalysisCompare') }}</el-menu-item>
          <el-menu-item index="/history-analysis/trend">{{ t('historyAnalysisTrend') }}</el-menu-item>
          <el-menu-item index="/history-analysis/anomaly">{{ t('historyAnalysisAnomaly') }}</el-menu-item>
          <el-menu-item index="/history-analysis/forecast">{{ t('historyAnalysisForecast') }}</el-menu-item>
          <el-menu-item index="/history-analysis/reports">{{ t('historyAnalysisReports') }}</el-menu-item>
        </el-sub-menu>
        <el-menu-item index="/users">
          <el-icon><UserFilled /></el-icon>
          <span>{{ t('users') }}</span>
        </el-menu-item>
        <el-menu-item index="/audit-logs">
          <el-icon><Document /></el-icon>
          <span>{{ t('auditLogs') }}</span>
        </el-menu-item>
        <el-menu-item index="/tickets">
          <el-icon><Tickets /></el-icon>
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
        <div class="header-text">
            <div class="greeting">{{ greeting }}</div>
            <div class="sub">{{ t('welcome') }}{{ authStore.user_Name }}</div>
          </div>
        <div class="actions">  
          <el-select :model-value="appStore.language" style="width: 120px" @change="onLanguageChange">
            <el-option label="简体中文" value="zh-CN" />
            <el-option label="English" value="en-US" />
            <el-option label="日本語" value="ja-JP"/>
            <el-option label="繁體中文" value="zh-TW"/>
            <el-option label="한국어" value="ko-KR"/>
          </el-select>
          
          <el-button plain @click="router.push('/user')">{{ t('userCenter') }}</el-button>
          <el-button type="danger" plain @click="onLogout">{{ t('logout') }}</el-button>
        </div>
      </header>
      <main class="content">
        <router-view v-slot="{ Component, route: currentRoute }">
          <keep-alive :include="cachedRouteNames">
            <component :is="Component" :key="currentRoute.path" />
          </keep-alive>
        </router-view>
      </main>
    </section>
  </div>
</template>

<script setup lang="ts">
import type { AppLanguage } from '../stores/app';
import { computed, ref, onMounted, watch } from 'vue';
import { ElMessage } from 'element-plus';
import { DataAnalysis, Document, Histogram, Key, Message, Operation, Setting, UserFilled, Tickets } from '@element-plus/icons-vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '../stores/auth';
import { useAppStore } from '../stores/app';
import { useI18nText } from '../i18n/useI18n';

const greeting = ref('');
const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();
const appStore = useAppStore();
const { t } = useI18nText();

const activePath = computed(() => route.path);
const defaultOpeneds = ['/history-analysis'];

const currentTitle = computed(() => {
  const titleKey = typeof route.meta.titleKey === 'string' ? route.meta.titleKey : '';
  if (titleKey) {
    return t(titleKey);
  }
  const title = typeof route.meta.title === 'string' ? route.meta.title : '';
  return title || t('appTitle');
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
      const label = key ? t(key) : String(record.meta.title || t('appTitle'));
      return {
        path: record.path,
        label,
        clickable: index < arr.length - 1
      };
    })
    .filter((item) => item.path !== '/');
});

const cachedRouteNames = [
  'history-analysis-snapshots',
  'history-analysis-compare',
  'history-analysis-trend',
  'history-analysis-anomaly',
  'history-analysis-forecast',
  'history-analysis-reports'
];

const onLanguageChange = (language: AppLanguage) => {
  appStore.setLanguage(language);
};

const onLogout = () => {
  authStore.logout();
  ElMessage.success(t('logoutsuccess'));
  router.push('/login/admin');
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
  font-size: 15px;
  font-weight: 500;
}

.menu :deep(.el-sub-menu__title) {
  color: #dbe8f4;
  border-radius: 8px;
  margin-bottom: 8px;
  font-size: 15px;
  font-weight: 500;
}

.menu :deep(.el-sub-menu .el-menu-item) {
  font-size: 14px;
  font-weight: 400;
  color: #333333;
}

.menu :deep(.el-menu-item:hover) {
  color: #1D4ED8;
  background: #F3F6FA;
  font-weight: 500;
}

.menu :deep(.el-menu-item.is-active) {
  color: #102a43;
  background: #e7f0ff;
  font-weight: 500;
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

.title-wrap {
  display: flex;
  flex-direction: column;
  gap: 4px;
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
