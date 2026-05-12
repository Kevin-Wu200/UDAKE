<template>
  <el-dialog v-model="visible" :title="title" width="400px">
    <el-form :model="form" ref="formRef" :rules="rules">
      <el-form-item :label="label" prop="content">
        <el-input v-model="form.content" type="textarea" :rows="3" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">{{ tc('dialogCancel') }}</el-button>
      <el-button type="primary" @click="submit" :loading="loading">{{ tc('dialogConfirm') }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import type { FormInstance, FormRules } from 'element-plus';
import { ref, reactive, computed } from 'vue';
import { useI18nText } from '../i18n/useI18n';

const { tc } = useI18nText();
const props = defineProps<{ type: 'approve' | 'reject' }>();
const emit = defineEmits(['confirm']);

const visible = ref(false);
const loading = ref(false);
const form = reactive({ content: '' });
const formRef = ref<FormInstance>();
const rules: FormRules<{ content: string }> = {
  content: [{ required: true, message: tc('requiredField'), trigger: 'blur' }]
};

const title = computed(() => props.type === 'approve' ? tc('confirmApprove') : tc('confirmReject'));
const label = computed(() => props.type === 'approve' ? tc('approvalNotes') : tc('rejectReason'));

const open = () => {
  form.content = '';
  visible.value = true;
};

const submit = async () => {
  await formRef.value?.validate();
  loading.value = true;
  emit('confirm', form.content);
};

const close = () => {
  visible.value = false;
  loading.value = false;
};

defineExpose({ open, close });
</script>
