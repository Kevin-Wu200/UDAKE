<template>
  <div class="page-card">
    <div class="page-header">
      <h2>{{ t('securityIpManagementTitle') }}</h2>
      <p class="subtitle">{{ t('securityIpManagementDesc') }}</p>
    </div>

    <!-- IP 规则管理标签页 -->
    <el-tabs v-model="activeTab" type="border-card">
      <el-tab-pane :label="t('securityIpRules')" name="rules">
        <div class="toolbar">
          <el-input v-model="rulesFilter.ipSearch" clearable style="width: 220px" :placeholder="t('securitySearchIp')" @clear="loadIpRules" @keyup.enter="loadIpRules" />
          <el-select v-model="rulesFilter.ruleType" clearable :placeholder="t('securityFilterType')" style="width: 140px" @change="loadIpRules">
            <el-option :label="t('securityAll')" value="" />
            <el-option :label="t('securityBlacklist')" value="blacklist" />
            <el-option :label="t('securityWhitelist')" value="whitelist" />
          </el-select>
          <el-select v-model="rulesFilter.isActive" clearable :placeholder="t('securityIsActive')" style="width: 120px" @change="loadIpRules">
            <el-option :label="t('securityAll')" value="" />
            <el-option :label="t('securityActive')" :value="true" />
            <el-option :label="t('securityInactive')" :value="false" />
          </el-select>
          <el-button type="primary" @click="loadIpRules">{{ t('query') }}</el-button>
          <el-button type="success" @click="openCreateDialog">{{ t('securityAddRule') }}</el-button>
        </div>

        <el-table :data="ipRulesList" border v-loading="rulesLoading">
          <el-table-column prop="ip_or_cidr" :label="t('securityIpOrCidr')" min-width="160" />
          <el-table-column prop="rule_type" :label="t('securityRuleType')" width="110">
            <template #default="{ row }">
              <el-tag :type="row.rule_type === 'blacklist' ? 'danger' : 'success'" size="small">
                {{ row.rule_type === 'blacklist' ? t('securityBlacklist') : t('securityWhitelist') }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="reason" :label="t('securityReason')" min-width="160" show-overflow-tooltip />
          <el-table-column prop="is_active" :label="t('securityIsActive')" width="90">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                {{ row.is_active ? t('securityActive') : t('securityInactive') }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="expires_at" :label="t('securityExpiresAt')" width="180">
            <template #default="{ row }">
              {{ row.expires_at || t('notSet') }}
            </template>
          </el-table-column>
          <el-table-column prop="created_at" :label="t('securityCreatedAt')" width="180" />
          <el-table-column :label="t('actions')" width="160" fixed="right">
            <template #default="{ row }">
              <div class="btn-group">
                <el-button size="small" type="primary" @click="openEditDialog(row)">{{ t('securityEditRule') }}</el-button>
                <el-button size="small" type="danger" @click="confirmDeleteRule(row)">{{ t('securityDeleteRule') }}</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination">
          <el-pagination
            background
            layout="total, prev, pager, next, sizes"
            :current-page="rulesPage"
            :page-size="rulesPageSize"
            :page-sizes="[10, 20, 50]"
            :total="rulesTotal"
            @current-change="(v: number) => { rulesPage = v; loadIpRules() }"
            @size-change="(v: number) => { rulesPageSize = v; loadIpRules() }"
          />
        </div>
      </el-tab-pane>

      <!-- 信誉度监控标签页 -->
      <el-tab-pane :label="t('securityReputation')" name="reputation">
        <div class="toolbar">
          <el-input v-model="repFilter.ipSearch" clearable style="width: 220px" :placeholder="t('securitySearchReputation')" @clear="loadIpReputations" @keyup.enter="loadIpReputations" />
          <el-input-number v-model="repFilter.minScore" :min="0" :max="100" :placeholder="t('securityMinScore')" style="width: 140px" controls-position="right" />
          <el-input-number v-model="repFilter.maxScore" :min="0" :max="100" :placeholder="t('securityMaxScore')" style="width: 140px" controls-position="right" />
          <el-button type="primary" @click="loadIpReputations">{{ t('query') }}</el-button>
        </div>

        <el-table :data="reputationList" border v-loading="repLoading">
          <el-table-column prop="ip_address" :label="t('securityIpAddress')" min-width="160" />
          <el-table-column prop="score" :label="t('securityReputationScore')" width="120" sortable>
            <template #default="{ row }">
              <el-progress
                :percentage="row.score"
                :color="scoreColor(row.score)"
                :stroke-width="18"
                :text-inside="true"
              />
            </template>
          </el-table-column>
          <el-table-column prop="risk_level" :label="t('securityRiskLevel')" width="110">
            <template #default="{ row }">
              <el-tag :type="riskTagType(row.risk_level)" size="small">
                {{ riskLabel(row.risk_level) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="success_count" :label="t('securitySuccessCount')" width="110" />
          <el-table-column prop="failed_count" :label="t('securityFailedCount')" width="110" />
          <el-table-column prop="rate_limited_count" :label="t('securityRateLimitedCount')" width="120" />
          <el-table-column prop="updated_at" :label="t('securityUpdatedAt')" width="180" />
        </el-table>

        <div class="pagination">
          <el-pagination
            background
            layout="total, prev, pager, next, sizes"
            :current-page="repPage"
            :page-size="repPageSize"
            :page-sizes="[10, 20, 50]"
            :total="repTotal"
            @current-change="(v: number) => { repPage = v; loadIpReputations() }"
            @size-change="(v: number) => { repPageSize = v; loadIpReputations() }"
          />
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 添加/编辑规则对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? t('securityEditRule') : t('securityAddRule')"
      width="520px"
      :close-on-click-modal="false"
    >
      <el-form ref="ruleFormRef" :model="ruleForm" :rules="ruleFormRules" label-width="130px">
        <el-form-item :label="t('securityIpOrCidr')" prop="ip_or_cidr">
          <el-input v-model="ruleForm.ip_or_cidr" :placeholder="t('securityIpOrCidr')" />
        </el-form-item>
        <el-form-item :label="t('securityRuleType')" prop="rule_type">
          <el-select v-model="ruleForm.rule_type" style="width: 100%">
            <el-option :label="t('securityBlacklist')" value="blacklist" />
            <el-option :label="t('securityWhitelist')" value="whitelist" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('securityReason')">
          <el-input v-model="ruleForm.reason" :placeholder="t('securityReason')" maxlength="255" show-word-limit />
        </el-form-item>
        <el-form-item :label="t('securityExpiresIn')">
          <el-input-number v-model="ruleForm.expires_in_seconds" :min="60" :placeholder="t('securityExpiresInHint')" style="width: 100%" controls-position="right" />
          <span class="form-hint">{{ t('securityExpiresInHint') }}</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">{{ t('cancel') }}</el-button>
        <el-button type="primary" :loading="submitting" @click="submitRule">{{ t('confirm') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, reactive } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import type { FormInstance, FormRules } from 'element-plus';
import { http } from '../services/http';
import { useI18nText } from '../i18n/useI18n';

const { t } = useI18nText();

// ── 状态 ──
const activeTab = ref('rules');

// IP 规则
const ipRulesList = ref<any[]>([]);
const rulesLoading = ref(false);
const rulesPage = ref(1);
const rulesPageSize = ref(20);
const rulesTotal = ref(0);
const rulesFilter = reactive({ ipSearch: '', ruleType: '', isActive: '' as any });

// IP 信誉度
const reputationList = ref<any[]>([]);
const repLoading = ref(false);
const repPage = ref(1);
const repPageSize = ref(20);
const repTotal = ref(0);
const repFilter = reactive({ ipSearch: '', minScore: undefined as number | undefined, maxScore: undefined as number | undefined });

// 对话框
const dialogVisible = ref(false);
const isEditing = ref(false);
const editingRuleId = ref<number | null>(null);
const submitting = ref(false);
const ruleFormRef = ref<FormInstance>();
const ruleForm = reactive({
  ip_or_cidr: '',
  rule_type: 'blacklist' as string,
  reason: '',
  expires_in_seconds: undefined as number | undefined,
});

const ruleFormRules: FormRules = {
  ip_or_cidr: [{ required: true, message: '请输入 IP 地址或 CIDR', trigger: 'blur' }],
  rule_type: [{ required: true, message: '请选择规则类型', trigger: 'change' }],
};

// ── 工具函数 ──
function scoreColor(score: number): string {
  if (score >= 90) return '#67c23a';
  if (score >= 60) return '#409eff';
  if (score >= 30) return '#e6a23c';
  if (score >= 15) return '#f56c6c';
  return '#ff0000';
}

function riskTagType(level: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  const map: Record<string, 'success' | 'warning' | 'danger' | 'info' | 'primary'> = {
    low: 'success',
    normal: 'primary',
    medium: 'warning',
    high: 'danger',
    critical: 'danger',
  };
  return map[level] || 'info';
}

function riskLabel(level: string): string {
  const map: Record<string, string> = {
    low: t('securityLow'),
    normal: t('securityNormal'),
    medium: t('securityMedium'),
    high: t('securityHigh'),
    critical: t('securityCritical'),
  };
  return map[level] || level;
}

// ── API 调用 ──
async function loadIpRules() {
  rulesLoading.value = true;
  try {
    const params: any = {
      page: rulesPage.value,
      page_size: rulesPageSize.value,
    };
    if (rulesFilter.ipSearch) params.ip_search = rulesFilter.ipSearch;
    if (rulesFilter.ruleType) params.rule_type = rulesFilter.ruleType;
    if (rulesFilter.isActive !== '' && rulesFilter.isActive !== undefined) params.is_active = rulesFilter.isActive;
    const res = await http.get('/admin/security/ip-rules', { params });
    const data = res.data?.data || {};
    ipRulesList.value = data.items || [];
    rulesTotal.value = data.total || 0;
  } catch {
    ElMessage.error(t('securityLoadError'));
  } finally {
    rulesLoading.value = false;
  }
}

async function loadIpReputations() {
  repLoading.value = true;
  try {
    const params: any = {
      page: repPage.value,
      page_size: repPageSize.value,
    };
    if (repFilter.ipSearch) params.ip_search = repFilter.ipSearch;
    if (repFilter.minScore !== undefined) params.min_score = repFilter.minScore;
    if (repFilter.maxScore !== undefined) params.max_score = repFilter.maxScore;
    const res = await http.get('/admin/security/ip-reputations', { params });
    const data = res.data?.data || {};
    reputationList.value = data.items || [];
    repTotal.value = data.total || 0;
  } catch {
    ElMessage.error(t('securityLoadError'));
  } finally {
    repLoading.value = false;
  }
}

function openCreateDialog() {
  isEditing.value = false;
  editingRuleId.value = null;
  ruleForm.ip_or_cidr = '';
  ruleForm.rule_type = 'blacklist';
  ruleForm.reason = '';
  ruleForm.expires_in_seconds = undefined;
  ruleFormRef.value?.resetFields();
  dialogVisible.value = true;
}

function openEditDialog(row: any) {
  isEditing.value = true;
  editingRuleId.value = row.id;
  ruleForm.ip_or_cidr = row.ip_or_cidr;
  ruleForm.rule_type = row.rule_type;
  ruleForm.reason = row.reason || '';
  ruleForm.expires_in_seconds = undefined;
  ruleFormRef.value?.resetFields();
  dialogVisible.value = true;
}

async function submitRule() {
  const valid = await ruleFormRef.value?.validate().catch(() => false);
  if (!valid) return;

  submitting.value = true;
  try {
    const payload: any = {
      ip_or_cidr: ruleForm.ip_or_cidr.trim(),
      rule_type: ruleForm.rule_type,
      reason: ruleForm.reason || undefined,
      expires_in_seconds: ruleForm.expires_in_seconds || undefined,
    };

    if (isEditing.value && editingRuleId.value) {
      await http.put(`/admin/security/ip-rules/${editingRuleId.value}`, payload);
      ElMessage.success(t('securityRuleUpdated'));
    } else {
      await http.post('/admin/security/ip-rules', payload);
      ElMessage.success(t('securityRuleCreated'));
    }
    dialogVisible.value = false;
    loadIpRules();
  } catch {
    // 错误由 http 拦截器统一处理
  } finally {
    submitting.value = false;
  }
}

async function confirmDeleteRule(row: any) {
  try {
    await ElMessageBox.confirm(t('securityDeleteRuleConfirm'), t('securityDeleteRule'), {
      confirmButtonText: t('confirm'),
      cancelButtonText: t('cancel'),
      type: 'warning',
    });
    await http.delete(`/admin/security/ip-rules/${row.id}`);
    ElMessage.success(t('securityRuleDeleted'));
    loadIpRules();
  } catch {
    // 取消或错误
  }
}

// ── 生命周期 ──
onMounted(() => {
  loadIpRules();
});
</script>

<style scoped>
.page-header {
  margin-bottom: 20px;
}
.page-header h2 {
  margin: 0 0 8px;
  font-size: 22px;
  font-weight: 600;
  color: #1d1d1f;
}
.subtitle {
  margin: 0;
  color: #86868b;
  font-size: 14px;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
.btn-group {
  display: flex;
  gap: 6px;
}
.form-hint {
  margin-left: 8px;
  font-size: 12px;
  color: #999;
}
</style>
