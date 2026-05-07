<template>
  <el-dialog v-model="visible" :title="title" width="400px">
    <el-form :model="form" ref="formRef" :rules="rules">
      <el-form-item :label="label" prop="content" :rules="[{ required: true, message: '此项必填' }]">
        <el-input v-model="form.content" type="textarea" :rows="3" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="submit" :loading="loading">确认</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import type { FormInstance, FormRules } from 'element-plus';
import { ref, reactive } from 'vue';

const props = defineProps<{ type: 'approve' | 'reject' }>();
const emit = defineEmits(['confirm']);

const visible = ref(false);
const loading = ref(false);
const form = reactive({ content: '' });
const formRef = ref<FormInstance>();
const rules: FormRules<{ content: string }> = {
  content: [{ required: true, message: '此项必填', trigger: 'blur' }]
};

const title = props.type === 'approve' ? '确认批准' : '确认拒绝';
const label = props.type === 'approve' ? '审批备注' : '拒绝原因';

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
