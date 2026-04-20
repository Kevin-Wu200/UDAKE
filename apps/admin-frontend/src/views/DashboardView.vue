<template>
  <div class="dashboard">
    <section class="metrics">
      <el-card class="metric-card">
        <template #header>{{ t('nearlyactiveuser') }}</template>
        <div class="metric-body">
          <span class="metric-icon">AU</span>
          <strong>{{ stats.activeUsers7d }}</strong>
        </div>
      </el-card>

      <el-card class="metric-card">
        <template #header>{{ t('enterpriseCount') }}</template>
        <div class="metric-body">
          <span class="metric-icon">CO</span>
          <strong>{{ stats.enterpriseTotal }} / {{ stats.enterpriseActive }}</strong>
        </div>
      </el-card>

      <el-card class="metric-card">
        <template #header>{{ t('todayRegistrations') }}</template>
        <div class="metric-body">
          <span class="metric-icon">RG</span>
          <strong>{{ stats.todayRegistrations }}</strong>
        </div>
      </el-card>

      <el-card class="metric-card">
        <template #header>{{ t('todayLogins') }}</template>
        <div class="metric-body">
          <span class="metric-icon">LG</span>
          <strong>{{ stats.todayLogins }}</strong>
        </div>
      </el-card>
    </section>

    <section class="charts">
      <el-card class="chart-card">
        <template #header>{{ t('userGrowthTrend') }}</template>
        <div ref="lineChartRef" class="chart"></div>
      </el-card>

      <el-card class="chart-card">
        <template #header>{{ t('keyUsage') }}</template>
        <div ref="pieChartRef" class="chart"></div>
      </el-card>
    </section>
  </div>
</template>

<script setup lang="ts">
import * as echarts from 'echarts';
import { nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { fetchDashboardStats } from '../services/http';
import { useI18nText } from '../i18n/useI18n';

const lineChartRef = ref<HTMLDivElement>();
const pieChartRef = ref<HTMLDivElement>();
const { t } = useI18nText();
const stats = reactive({
  userGrowth: [] as Array<{ date: string; count: number }>,
  keyUsage: { used: 0, unused: 0 },
  activeUsers7d: 0,
  enterpriseTotal: 0,
  enterpriseActive: 0,
  todayRegistrations: 0,
  todayLogins: 0
});

let lineChart: echarts.ECharts | null = null;
let pieChart: echarts.ECharts | null = null;
let resizeObserver: ResizeObserver | null = null;

const renderCharts = () => {
  if (!lineChartRef.value || !pieChartRef.value) {
    return;
  }

  lineChart ??= echarts.init(lineChartRef.value);
  pieChart ??= echarts.init(pieChartRef.value);

  lineChart.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: stats.userGrowth.map((item) => item.date)
    },
    yAxis: {
      type: 'value',
      name: t('usernum')
    },
    series: [
      {
        data: stats.userGrowth.map((item) => item.count),
        type: 'line',
        smooth: true,
        lineStyle: { width: 3, color: '#007d73' },
        areaStyle: { color: 'rgba(0,125,115,0.15)' }
      }
    ]
  });

  pieChart.setOption({
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)'
    },
    series: [
      {
        type: 'pie',
        radius: ['44%', '70%'],
        data: [
          { value: stats.keyUsage.used, name: t('used') },
          { value: stats.keyUsage.unused, name: t('unused') }
        ],
        label: {
          formatter: '{b}\n{d}%'
        }
      }
    ]
  });
};

const handleResize = () => {
  lineChart?.resize();
  pieChart?.resize();
};

const loadData = async () => {
  try {
    const res = await fetchDashboardStats();
    Object.assign(stats, res);
    await nextTick();
    renderCharts();
  } catch {
    ElMessage.error(t('statisticloadfailed'));
  }
};

onMounted(() => {
  loadData();
  window.addEventListener('resize', handleResize);
  resizeObserver = new ResizeObserver(() => handleResize());
  if (lineChartRef.value) {
    resizeObserver.observe(lineChartRef.value);
  }
  if (pieChartRef.value) {
    resizeObserver.observe(pieChartRef.value);
  }
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize);
  resizeObserver?.disconnect();
  lineChart?.dispose();
  pieChart?.dispose();
});
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.metric-card {
  border-radius: 14px;
}

.metric-body {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 20px;
}

.metric-body strong {
  font-size: 30px;
  color: #0f172a;
}

.metric-icon {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #d5f5f2;
  color: #0f766e;
  font-size: 13px;
  font-weight: 700;
}

.charts {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 12px;
}

.chart-card {
  border-radius: 14px;
}

.chart {
  height: 320px;
}

@media (max-width: 1080px) {
  .metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .charts {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .metrics {
    grid-template-columns: 1fr;
  }

  .chart {
    height: 280px;
  }
}
</style>
