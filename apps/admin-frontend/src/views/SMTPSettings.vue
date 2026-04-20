<template>
  <div class="smtp-settings">
    <el-card class="settings-card" v-loading="loading">
      <template #header>
        <h2>{{ t('smtpserviceconfig') }}</h2>
      </template>

      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-form-item :label="t('serviceaddress')" prop="host">
          <el-input v-model="form.host" placeholder="如 smtp.example.com" />
        </el-form-item>
        <el-form-item :label="t('port')" prop="port">
          <el-input-number v-model="form.port" :min="1" :max="65535" style="width: 220px" />
        </el-form-item>
        <el-form-item :label="t('encryption')" prop="encryption">
          <el-radio-group v-model="form.encryption">
            <el-radio value="TLS">TLS</el-radio>
            <el-radio value="SSL">SSL</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item :label="t('username')" prop="username">
          <el-input v-model="form.username" :placeholder="t('email')" />
        </el-form-item>
        <el-form-item :label="t('password')" prop="password">
          <el-input v-model="form.password" type="password" show-password :placeholder="t('smtppassword')" />
        </el-form-item>
      </el-form>

      <div class="actions">
        <el-button :loading="testing" @click="handleTest">{{ t('connettest') }}</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">{{ t('saveconfig') }}</el-button>
      </div>

      <el-alert
        v-if="form.updated_at"
        class="updated-tip"
        type="info"
        :closable="false"
        :title="`${t('nearupdate')}：${form.updated_at}`"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import type { FormInstance, FormRules } from 'element-plus';
import type { SMTPConfig } from '../types/admin';
import { onMounted, reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';
import type { AxiosError } from 'axios';
import { fetchSmtpConfig, saveSmtpConfig, testSmtpConnection } from '../services/smtpApi';
import { useI18nText } from '../i18n/useI18n';

const loading = ref(false);
const saving = ref(false);
const testing = ref(false);
const formRef = ref<FormInstance>();
const { t } = useI18nText();

const form = reactive<SMTPConfig>({
  host: '',
  port: 587,
  encryption: 'TLS',
  username: '',
  password: '',
  updated_at: ''
});

const rules: FormRules<typeof form> = {
  host: [{ required: true, message: t('address_error'), trigger: 'blur' }],
  port: [{ required: true, type: 'number', message: t('port_error'), trigger: 'change' }],
  encryption: [{ required: true, message: t('encryption_error'), trigger: 'change' }],
  username: [{ required: true, message: t('username_error'), trigger: 'blur' }],
  password: [{ required: true, message: t('password_error'), trigger: 'blur' }]
};

function resolveErrorMessage(error: unknown, fallback: string): string {
  const axiosError = error as AxiosError<{ message?: string; detail?: string | { message?: string } }>;
  const message = axiosError?.response?.data?.message;
  if (typeof message === 'string' && message.trim()) {
    return message.trim();
  }
  const detail = axiosError?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) {
    return detail.trim();
  }
  if (typeof detail === 'object' && typeof detail?.message === 'string' && detail.message.trim()) {
    return detail.message.trim();
  }
  if (error instanceof Error && error.message.trim()) {
    return error.message.trim();
  }
  return fallback;
}

const loadConfig = async () => {
  loading.value = true;
  try {
    const res = await fetchSmtpConfig();
    Object.assign(form, res);
  } catch (error) {
    ElMessage.error(resolveErrorMessage(error, t('loadfailed')));
  } finally {
    loading.value = false;
  }
};

const handleTest = async () => {
  if (!formRef.value) {
    return;
  }
  try {
    await formRef.value.validate();
    testing.value = true;
    const result = await testSmtpConnection(form);
    ElMessage.success(`连接测试成功，耗时 ${result.latencyMs}ms`);
  } catch (error) {
    ElMessage.error(resolveErrorMessage(error, '连接测试失败'));
  } finally {
    testing.value = false;
  }
};

const handleSave = async () => {
  if (!formRef.value) {
    return;
  }
  try {
    await formRef.value.validate();
    saving.value = true;
    const res = await saveSmtpConfig(form);
    Object.assign(form, res);
    ElMessage.success('SMTP配置已保存（密码已脱敏存储）');
  } catch (error) {
    ElMessage.error(resolveErrorMessage(error, '保存失败，请检查配置后重试'));
  } finally {
    saving.value = false;
  }
};

onMounted(() => {
  void loadConfig();
});
</script>

<style scoped>
.smtp-settings {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.settings-card {
  border-radius: 12px;
}

.settings-card h2 {
  margin: 0;
  font-size: 20px;
}

.actions {
  margin-top: 12px;
  display: flex;
  gap: 12px;
}

.updated-tip {
  margin-top: 14px;
}

.el-form-item__label {
  white-space: nowrap;
}
</style>
