<template>
  <div class="history-analysis-layout">
    <section class="page-card history-global-card">
      <div class="toolbar">
        <el-input
          v-model="globalForm.datasetId"
          :placeholder="t('historyAnalysisDatasetId')"
          clearable
          style="width: 280px"
          @change="syncRouteQuery"
        />
        <el-input
          v-model="globalForm.versionA"
          :placeholder="t('historyAnalysisVersionA')"
          clearable
          style="width: 160px"
          @change="syncRouteQuery"
        />
        <el-input
          v-model="globalForm.versionB"
          :placeholder="t('historyAnalysisVersionB')"
          clearable
          style="width: 160px"
          @change="syncRouteQuery"
        />
        <el-button @click="syncRouteQuery">{{ t('historyAnalysisApplyQuery') }}</el-button>
        <el-button type="warning" plain @click="clearCurrentCache">{{ t('historyAnalysisClearCurrentCache') }}</el-button>
      </div>
      <div class="hint">
        {{ t('historyAnalysisDataTransferHint') }}
      </div>
    </section>

    <section class="page-card history-tabs-card">
      <el-tabs v-model="activeTab" @tab-click="onTabClick">
        <el-tab-pane
          v-for="item in tabs"
          :key="item.name"
          :name="item.name"
          :label="t(item.labelKey)"
        />
      </el-tabs>
    </section>

    <router-view />
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from 'vue';
import type { TabsPaneContext } from 'element-plus';
import { useRoute, useRouter } from 'vue-router';
import { useI18nText } from '../../i18n/useI18n';
import {
  HISTORY_SECTIONS,
  type HistorySection,
  useHistoryAnalysisStore
} from '../../stores/historyAnalysis';

const route = useRoute();
const router = useRouter();
const historyStore = useHistoryAnalysisStore();
const { t } = useI18nText();

const tabs: Array<{ name: HistorySection; routePath: string; labelKey: string }> = [
  { name: 'snapshots', routePath: '/history-analysis/snapshots', labelKey: 'historyAnalysisSnapshots' },
  { name: 'compare', routePath: '/history-analysis/compare', labelKey: 'historyAnalysisCompare' },
  { name: 'trend', routePath: '/history-analysis/trend', labelKey: 'historyAnalysisTrend' },
  { name: 'anomaly', routePath: '/history-analysis/anomaly', labelKey: 'historyAnalysisAnomaly' },
  { name: 'forecast', routePath: '/history-analysis/forecast', labelKey: 'historyAnalysisForecast' },
  { name: 'reports', routePath: '/history-analysis/reports', labelKey: 'historyAnalysisReports' }
];

const normalizeDatasetId = (value: unknown): string => {
  const text = typeof value === 'string' ? value.trim() : '';
  return /^[a-zA-Z0-9_-]{0,64}$/.test(text) ? text : '';
};

const normalizeVersion = (value: unknown): string => {
  const text = typeof value === 'string' ? value.trim() : '';
  return /^\d{0,6}$/.test(text) ? text : '';
};

const getCurrentSection = (): HistorySection => {
  const name = route.name;
  if (typeof name !== 'string') {
    return 'snapshots';
  }

  const map: Record<string, HistorySection> = {
    'history-analysis-snapshots': 'snapshots',
    'history-analysis-compare': 'compare',
    'history-analysis-trend': 'trend',
    'history-analysis-anomaly': 'anomaly',
    'history-analysis-forecast': 'forecast',
    'history-analysis-reports': 'reports'
  };

  return map[name] || 'snapshots';
};

const activeTab = computed<HistorySection>(() => getCurrentSection());

const globalForm = reactive({
  datasetId: '',
  versionA: '',
  versionB: ''
});

const applyFromRouteAndStore = () => {
  const section = getCurrentSection();
  const storeState = historyStore.pageState[section];
  const routeQuery = route.query;

  globalForm.datasetId = normalizeDatasetId(routeQuery.datasetId) || storeState.datasetId;
  globalForm.versionA = normalizeVersion(routeQuery.versionA) || storeState.versionA;
  globalForm.versionB = normalizeVersion(routeQuery.versionB) || storeState.versionB;

  historyStore.patchPageState(section, {
    datasetId: globalForm.datasetId,
    versionA: globalForm.versionA,
    versionB: globalForm.versionB
  });
};

const syncRouteQuery = async () => {
  const section = getCurrentSection();
  historyStore.patchPageState(section, {
    datasetId: normalizeDatasetId(globalForm.datasetId),
    versionA: normalizeVersion(globalForm.versionA),
    versionB: normalizeVersion(globalForm.versionB)
  });

  const state = historyStore.pageState[section];
  const nextQuery: Record<string, string> = {};
  if (state.datasetId) {
    nextQuery.datasetId = state.datasetId;
  }
  if (state.versionA) {
    nextQuery.versionA = state.versionA;
  }
  if (state.versionB) {
    nextQuery.versionB = state.versionB;
  }

  await router.replace({ query: nextQuery });
};

const onTabClick = async (tab: TabsPaneContext) => {
  const next = tabs.find((item) => item.name === tab.paneName);
  if (!next) {
    return;
  }

  const currentState = historyStore.pageState[next.name];
  await router.push({
    path: next.routePath,
    query: {
      datasetId: currentState.datasetId,
      versionA: currentState.versionA,
      versionB: currentState.versionB
    }
  });
};

const clearCurrentCache = () => {
  historyStore.clearCache(getCurrentSection());
};

watch(
  () => [route.fullPath, route.name],
  () => {
    const current = getCurrentSection();
    if (!HISTORY_SECTIONS.includes(current)) {
      return;
    }
    applyFromRouteAndStore();
  },
  { immediate: true }
);
</script>

<style scoped>
.history-analysis-layout {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.history-global-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.history-tabs-card :deep(.el-tabs__header) {
  margin-bottom: 0;
}

.hint {
  color: #64748b;
  font-size: 13px;
}
</style>
