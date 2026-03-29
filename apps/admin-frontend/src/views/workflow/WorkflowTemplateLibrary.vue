<template>
  <div class="panel-card">
    <div class="panel-header">
      <div class="panel-title">模板库</div>
      <el-button link type="primary" :loading="loading" @click="loadTemplates">刷新</el-button>
    </div>

    <div class="template-filters">
      <el-input v-model="keyword" placeholder="搜索模板名称/标签" clearable />
      <el-input v-model="recommendTags" placeholder="推荐标签（逗号分隔）" clearable />
      <div class="filter-actions">
        <el-button size="small" @click="loadRecommendations">推荐</el-button>
        <el-button size="small" @click="loadTemplates">查询</el-button>
      </div>
    </div>

    <el-scrollbar height="280px">
      <div class="template-list">
        <div v-for="item in filteredTemplates" :key="item.template_id" class="template-item">
          <div class="row-top">
            <div>
              <div class="name">{{ item.name }}</div>
              <div class="meta">
                {{ item.category }} · 使用 {{ item.usage_count }} 次 · 评分 {{ item.rating_average.toFixed(1) }}
              </div>
            </div>
            <el-tag :type="item.shared ? 'success' : 'info'">{{ item.shared ? '共享' : '私有' }}</el-tag>
          </div>
          <div class="desc">{{ item.description || '暂无描述' }}</div>
          <div class="tags">
            <el-tag v-for="tag in item.tags" :key="`${item.template_id}_${tag}`" size="small">{{ tag }}</el-tag>
          </div>
          <div class="actions">
            <el-button size="small" type="primary" @click="emit('apply-template', item)">应用</el-button>
            <el-button size="small" @click="instantiate(item)">实例化</el-button>
            <el-button size="small" @click="toggleShare(item)">
              {{ item.shared ? '取消共享' : '共享' }}
            </el-button>
            <el-button size="small" @click="rate(item)">评分+1</el-button>
          </div>
        </div>
      </div>
    </el-scrollbar>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { workflowService } from '../../services/WorkflowService';
import type { WorkflowTemplate } from '../../types/workflow';

const emit = defineEmits<{
  'apply-template': [template: WorkflowTemplate];
  'instantiated': [workflowId: string];
}>();

const loading = ref(false);
const templates = ref<WorkflowTemplate[]>([]);
const keyword = ref('');
const recommendTags = ref('采样,插值');

const filteredTemplates = computed(() => {
  const query = keyword.value.trim().toLowerCase();
  if (!query) {
    return templates.value;
  }
  return templates.value.filter((item) => {
    const searchable = [item.name, item.description, item.category, ...(item.tags || [])]
      .join(' ')
      .toLowerCase();
    return searchable.includes(query);
  });
});

const loadTemplates = async () => {
  loading.value = true;
  try {
    const [normal, market] = await Promise.all([
      workflowService.listTemplates({ limit: 200 }),
      workflowService.getMarketplace(20)
    ]);
    const merged = [...normal.templates, ...market.items];
    const map = new Map<string, WorkflowTemplate>();
    merged.forEach((item) => map.set(item.template_id, item));
    templates.value = Array.from(map.values()).sort(
      (a, b) => b.rating_average - a.rating_average || b.usage_count - a.usage_count
    );
  } catch {
    ElMessage.error('加载模板库失败');
  } finally {
    loading.value = false;
  }
};

const loadRecommendations = async () => {
  const tags = recommendTags.value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);

  if (!tags.length) {
    ElMessage.warning('请输入推荐标签');
    return;
  }

  loading.value = true;
  try {
    const response = await workflowService.recommendTemplates(tags, undefined, 20);
    templates.value = response.recommendations.map((item) => item.template);
    ElMessage.success(`已按标签推荐 ${response.count} 个模板`);
  } catch {
    ElMessage.error('推荐模板失败');
  } finally {
    loading.value = false;
  }
};

const instantiate = async (template: WorkflowTemplate) => {
  try {
    const record = await workflowService.instantiateTemplate(template.template_id, `${template.name}_实例`);
    ElMessage.success('模板实例化成功');
    emit('instantiated', record.workflow_id);
    await loadTemplates();
  } catch {
    ElMessage.error('实例化模板失败');
  }
};

const toggleShare = async (template: WorkflowTemplate) => {
  try {
    await workflowService.shareTemplate(template.template_id, !template.shared);
    ElMessage.success('模板共享状态已更新');
    await loadTemplates();
  } catch {
    ElMessage.error('更新模板共享状态失败');
  }
};

const rate = async (template: WorkflowTemplate) => {
  try {
    const nextRating = Math.min(5, Math.max(1, Number((template.rating_average || 0) + 1)));
    await workflowService.rateTemplate(template.template_id, nextRating, 'admin-console', '页面内快速评分');
    ElMessage.success('评分已提交');
    await loadTemplates();
  } catch {
    ElMessage.error('模板评分失败');
  }
};

onMounted(() => {
  loadTemplates();
});
</script>

<style scoped>
.panel-card {
  border: 1px solid #d9e2ef;
  border-radius: 10px;
  background: #fff;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.panel-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.template-filters {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.filter-actions {
  display: flex;
  gap: 8px;
}

.template-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.template-item {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.row-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.name {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
}

.meta,
.desc {
  font-size: 12px;
  color: #64748b;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
</style>
