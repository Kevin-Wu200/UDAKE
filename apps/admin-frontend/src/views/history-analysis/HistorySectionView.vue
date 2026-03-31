<template>
  <section class="page-card history-section-card">
    <header class="section-header">
      <div>
        <h3>{{ t(sectionConfig.titleKey) }}</h3>
        <p>{{ t(sectionConfig.descriptionKey) }}</p>
      </div>
      <div class="header-actions">
        <el-tag type="info">{{ cacheStatusText }}</el-tag>
        <el-button size="small" @click="persistCurrentResult">{{ t('historyAnalysisPersistDemoData') }}</el-button>
      </div>
    </header>

    <div class="toolbar">
      <el-input
        v-model="form.datasetId"
        :placeholder="t('historyAnalysisDatasetId')"
        clearable
        style="width: 280px"
      />
      <el-input
        v-model="form.versionA"
        :placeholder="t('historyAnalysisVersionA')"
        clearable
        style="width: 160px"
      />
      <el-input
        v-model="form.versionB"
        :placeholder="t('historyAnalysisVersionB')"
        clearable
        style="width: 160px"
      />
      <el-button type="primary" @click="applyState">{{ t('historyAnalysisApplyState') }}</el-button>
      <el-button @click="goCompareWithCurrent">{{ t('historyAnalysisJumpCompare') }}</el-button>
    </div>

    <el-alert
      v-if="validationMessage"
      :title="validationMessage"
      type="warning"
      show-icon
      :closable="false"
      class="state-alert"
    />

    <el-descriptions :column="2" border>
      <el-descriptions-item :label="t('historyAnalysisDatasetId')">{{ form.datasetId || '-' }}</el-descriptions-item>
      <el-descriptions-item :label="t('historyAnalysisVersionA')">{{ form.versionA || '-' }}</el-descriptions-item>
      <el-descriptions-item :label="t('historyAnalysisVersionB')">{{ form.versionB || '-' }}</el-descriptions-item>
      <el-descriptions-item :label="t('historyAnalysisUpdatedAt')">{{ updatedAtText }}</el-descriptions-item>
    </el-descriptions>
  </section>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { useI18nText } from '../../i18n/useI18n';
import { type HistorySection, useHistoryAnalysisStore } from '../../stores/historyAnalysis';

const props = defineProps<{ section: HistorySection }>();

const route = useRoute();
const router = useRouter();
const historyStore = useHistoryAnalysisStore();
const { t } = useI18nText();

const form = reactive({
  datasetId: '',
  versionA: '',
  versionB: ''
});

const sectionConfig = computed(() => {
  const map: Record<HistorySection, { titleKey: string; descriptionKey: string }> = {
    snapshots: {
      titleKey: 'historyAnalysisSnapshots',
      descriptionKey: 'historyAnalysisSnapshotsDesc'
    },
    compare: {
      titleKey: 'historyAnalysisCompare',
      descriptionKey: 'historyAnalysisCompareDesc'
    },
    trend: {
      titleKey: 'historyAnalysisTrend',
      descriptionKey: 'historyAnalysisTrendDesc'
    },
    anomaly: {
      titleKey: 'historyAnalysisAnomaly',
      descriptionKey: 'historyAnalysisAnomalyDesc'
    },
    forecast: {
      titleKey: 'historyAnalysisForecast',
      descriptionKey: 'historyAnalysisForecastDesc'
    },
    reports: {
      titleKey: 'historyAnalysisReports',
      descriptionKey: 'historyAnalysisReportsDesc'
    }
  };
  return map[props.section];
});

const normalizeDatasetId = (value: string): string => {
  const clean = value.trim();
  return /^[a-zA-Z0-9_-]{0,64}$/.test(clean) ? clean : '';
};

const normalizeVersion = (value: string): string => {
  const clean = value.trim();
  return /^\d{0,6}$/.test(clean) ? clean : '';
};

const validationMessage = computed(() => {
  if (form.datasetId && !normalizeDatasetId(form.datasetId)) {
    return t('historyAnalysisInvalidDatasetId');
  }

  if ((form.versionA && !normalizeVersion(form.versionA)) || (form.versionB && !normalizeVersion(form.versionB))) {
    return t('historyAnalysisInvalidVersion');
  }

  return '';
});

const cacheStatusText = computed(() => {
  const cache = historyStore.getCache(props.section);
  if (!cache) {
    return t('historyAnalysisCacheEmpty');
  }

  return `${t('historyAnalysisCacheHit')} ${new Date(cache.updatedAt).toLocaleString()}`;
});

const updatedAtText = computed(() => {
  const cache = historyStore.getCache(props.section);
  if (!cache) {
    return '-';
  }
  return new Date(cache.updatedAt).toLocaleString();
});

const syncFromStoreAndRoute = () => {
  const fromStore = historyStore.pageState[props.section];
  const fromRoute = {
    datasetId: typeof route.query.datasetId === 'string' ? route.query.datasetId : '',
    versionA: typeof route.query.versionA === 'string' ? route.query.versionA : '',
    versionB: typeof route.query.versionB === 'string' ? route.query.versionB : ''
  };

  form.datasetId = normalizeDatasetId(fromRoute.datasetId) || fromStore.datasetId;
  form.versionA = normalizeVersion(fromRoute.versionA) || fromStore.versionA;
  form.versionB = normalizeVersion(fromRoute.versionB) || fromStore.versionB;
};

const applyState = async () => {
  const nextDatasetId = normalizeDatasetId(form.datasetId);
  const nextVersionA = normalizeVersion(form.versionA);
  const nextVersionB = normalizeVersion(form.versionB);

  if (form.datasetId && !nextDatasetId) {
    ElMessage.warning(t('historyAnalysisInvalidDatasetId'));
    return;
  }
  if ((form.versionA && !nextVersionA) || (form.versionB && !nextVersionB)) {
    ElMessage.warning(t('historyAnalysisInvalidVersion'));
    return;
  }

  historyStore.patchPageState(props.section, {
    datasetId: nextDatasetId,
    versionA: nextVersionA,
    versionB: nextVersionB
  });

  await router.replace({
    query: {
      datasetId: nextDatasetId,
      versionA: nextVersionA,
      versionB: nextVersionB
    }
  });

  ElMessage.success(t('historyAnalysisStateSaved'));
};

const persistCurrentResult = () => {
  historyStore.setCache(props.section, {
    datasetId: historyStore.pageState[props.section].datasetId,
    versionA: historyStore.pageState[props.section].versionA,
    versionB: historyStore.pageState[props.section].versionB,
    section: props.section
  });
  ElMessage.success(t('historyAnalysisCacheSaved'));
};

const goCompareWithCurrent = async () => {
  const state = historyStore.pageState[props.section];
  await router.push({
    path: '/history-analysis/compare',
    query: {
      datasetId: state.datasetId,
      versionA: state.versionA,
      versionB: state.versionB
    }
  });
};

watch(
  () => [route.fullPath, props.section],
  () => {
    syncFromStoreAndRoute();
  },
  { immediate: true }
);
</script>

<style scoped>
.history-section-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.section-header p {
  margin-top: 4px;
  color: #64748b;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.state-alert {
  margin-top: -4px;
}

@media (max-width: 960px) {
  .section-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
