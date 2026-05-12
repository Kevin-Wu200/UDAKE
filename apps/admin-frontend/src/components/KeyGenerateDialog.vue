<template>
  <el-dialog v-model="visible" :title="tc('batchGenerateCompanyKeys')" width="600px" @close="handleClose">
    <el-form ref="formRef" :model="form" :rules="rules" label-width="120px">
      <el-form-item :label="tc('keyType')" prop="type">
        <el-radio-group v-model="form.type">
          <el-radio
            v-for="item in availableTypes"
            :key="item.value"
            :value="item.value"
          >
            {{ item.label }}
          </el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item :label="tc('generateNum')" prop="count">
        <el-input-number v-model="form.count" :min="1" :max="maxCountPerCreate" :step="10" />
        <div class="form-tip">{{ tc('keyQuota') }}</div>
        <div class="form-tip">{{ tc('keyLimit') }}{{ remainingQuota }}</div>
      </el-form-item>

      <el-form-item :label="tc('companyInfo')">
        <el-descriptions :column="1" border>
          <el-descriptions-item :label="tc('companyName')">{{ company.name }}</el-descriptions-item>
          <el-descriptions-item :label="tc('companyId')">{{ company.id }}</el-descriptions-item>
        </el-descriptions>
      </el-form-item>

      <el-form-item :label="tc('preview')">
        <el-button @click="handlePreview" :disabled="!form.type">{{ tc('preview') }}</el-button>
        <div v-if="previewKeys.length > 0" class="preview-keys">
          <div v-for="key in previewKeys" :key="key" class="preview-key">{{ key }}</div>
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="handleClose">{{ tc('dialogCancel') }}</el-button>
      <el-button type="primary" :loading="loading" :disabled="createDisabledByQuota" @click="handleConfirm">{{ tc('dialogConfirm') }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import type { FormInstance, FormRules } from 'element-plus';
import { computed, reactive, ref, watch } from 'vue';
import { ElMessage } from 'element-plus';
import { useAuthStore } from '../stores/auth';
import { batchGenerateCompanyKeys, previewCompanyKeys } from '../services/http';
import { useI18nText } from '../i18n/useI18n';

const { tc } = useI18nText();
const props = defineProps<{
  modelValue: boolean;
  availableTypes?: Array<'enterprise_trial' | 'enterprise_standard'>;
  remainingQuota?: number;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
  (e: 'success', keys: string[]): void;
}>();

const authStore = useAuthStore();
const visible = computed({
  get: () => props.modelValue,
  set: (val: boolean) => emit('update:modelValue', val)
});
const loading = ref(false);
const formRef = ref<FormInstance>();
const form = reactive({
  type: 'enterprise_trial' as 'enterprise_trial' | 'enterprise_standard',
  count: 10
});
const previewKeys = ref<string[]>([]);
const company = computed(() => authStore.currentCompany);
const availableTypes = computed(() => {
  const current: Array<'enterprise_trial' | 'enterprise_standard'> = props.availableTypes?.length
    ? props.availableTypes
    : ['enterprise_trial', 'enterprise_standard'];
  return current.map((item) => ({
    value: item,
    label: item === 'enterprise_trial' ? tc('companyTrail') : tc('companyStandard')
  }));
});
const remainingQuota = computed(() => Math.max(0, props.remainingQuota ?? 0));
const createDisabledByQuota = computed(() => remainingQuota.value <= 0);
const maxCountPerCreate = computed(() => Math.max(1, Math.min(1000, remainingQuota.value || 1000)));

watch(
  availableTypes,
  (next) => {
    const allowed = next.map((item) => item.value);
    if (!allowed.includes(form.type)) {
      form.type = allowed[0] ?? 'enterprise_trial';
    }
  },
  { immediate: true }
);

const rules: FormRules<typeof form> = {
  type: [{ required: true, message: tc('keyTypeRequired'), trigger: 'change' }],
  count: [
    { required: true, message: tc('keyNumRequired'), trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (typeof value !== 'number' || value < 1 || value > maxCountPerCreate.value) {
          callback(new Error(`${tc('numScope')} 1-${maxCountPerCreate.value}`));
          return;
        }
        callback();
      },
      trigger: 'blur'
    }
  ]
};

const handlePreview = async () => {
  try {
    previewKeys.value = await previewCompanyKeys({
      type: form.type,
      count: form.count
    });
  } catch {
    ElMessage.error(tc('previewFailed'));
  }
};

const handleConfirm = async () => {
  if (!formRef.value) {
    return;
  }
  try {
    await formRef.value.validate();
    if (createDisabledByQuota.value) {
      ElMessage.warning(tc('quotaLimited'));
      return;
    }
    if (form.count > remainingQuota.value) {
      ElMessage.warning(tc('quotaOvered'));
      return;
    }
    loading.value = true;
    const created = await batchGenerateCompanyKeys({
      company_id: company.value.id,
      type: form.type,
      count: form.count
    });
    ElMessage.success(tc('generateSuccess', { createNum: created.length }));
    emit(
      'success',
      created.map((item) => item.product_key)
    );
    handleClose();
  } catch {
    ElMessage.error(tc('generateFailed'));
  } finally {
    loading.value = false;
  }
};

const handleClose = () => {
  visible.value = false;
  form.type = availableTypes.value[0]?.value ?? 'enterprise_trial';
  form.count = 10;
  previewKeys.value = [];
};
</script>

<style scoped>
.form-tip {
  margin-top: 8px;
  color: #64748b;
  font-size: 12px;
}

.preview-keys {
  margin-top: 12px;
  max-height: 160px;
  overflow: auto;
  padding: 8px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.preview-key {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  line-height: 1.8;
}
</style>
