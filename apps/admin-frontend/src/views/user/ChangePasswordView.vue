<template>
  <div class="page-card page-wrap">
    <h2>{{ t('changepassword') }}</h2>
    <p class="desc">{{ t('passwordDescription') }}</p>

    <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent>
      <el-form-item :label="t('oldPassword')" prop="oldPassword">
        <el-input v-model="form.oldPassword" type="password" show-password :placeholder="t('enterOldPassword')" />
      </el-form-item>

      <el-form-item :label="t('newPassword')" prop="newPassword">
        <el-input v-model="form.newPassword" type="password" show-password :placeholder="t('enterNewPassword')" />
      </el-form-item>

      <div class="strength-box">
        <div>
          {{ t('passwordStrength') }}：
          <span :style="{ color: passwordStrength.color }">{{ passwordStrength.label }}</span>
        </div>
        <el-progress :percentage="passwordStrength.score" :stroke-width="8" :color="passwordStrength.color" />
        <small>{{ t('passwordRequirements') }}</small>
      </div>

      <el-form-item :label="t('confirmNewPassword')" prop="confirmPassword">
        <el-input v-model="form.confirmPassword" type="password" show-password :placeholder="t('enterConfirmPassword')" />
      </el-form-item>

      <div class="actions">
        <el-button type="primary" :loading="submitting" @click="onSubmit">{{ t('confirmModify') }}</el-button>
      </div>
    </el-form>
  </div>
</template>

<script setup lang="ts">
import type { FormInstance, FormRules } from 'element-plus';
import { computed, reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { useRouter } from 'vue-router';
import { useAuthStore } from '../../stores/auth';
import { changePassword } from '../../services/userAuthApi';
import { evaluatePasswordStrength } from '../../utils/auth';
import { useI18nText } from '../../i18n/useI18n';

const { t } = useI18nText();

interface PasswordForm {
  oldPassword: string;
  newPassword: string;
  confirmPassword: string;
}

const router = useRouter();
const authStore = useAuthStore();
const formRef = ref<FormInstance>();
const submitting = ref(false);

const form = reactive<PasswordForm>({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
});

const passwordStrength = computed(() => evaluatePasswordStrength(form.newPassword));

const validatePasswordStrength = (_rule: unknown, value: string, callback: (error?: Error) => void) => {
  const strength = evaluatePasswordStrength(value);
  if (strength.level === 'weak') {
    callback(new Error(t('passwordStrengthWeak')));
    return;
  }
  callback();
};

const validateConfirmPassword = (_rule: unknown, value: string, callback: (error?: Error) => void) => {
  if (!value) {
    callback(new Error(t('enterConfirmPassword')));
    return;
  }
  if (value !== form.newPassword) {
    callback(new Error(t('passwordsDoNotMatch')));
    return;
  }
  callback();
};

const rules: FormRules<PasswordForm> = {
  oldPassword: [{ required: true, message: t('enterOldPassword'), trigger: 'blur' }],
  newPassword: [
    { required: true, message: t('enterNewPassword'), trigger: 'blur' },
    { validator: validatePasswordStrength, trigger: 'blur' }
  ],
  confirmPassword: [{ validator: validateConfirmPassword, trigger: 'blur' }]
};

const onSubmit = async () => {
  if (!formRef.value) {
    return;
  }

  try {
    await formRef.value.validate();
    submitting.value = true;
    await changePassword(form.oldPassword, form.newPassword, form.confirmPassword);

    ElMessage.success(t('passwordChangeSuccess'));
    await authStore.logoutWithApi();
    await router.replace('/user/login');
  } catch {
    // 错误由拦截器提示
  } finally {
    submitting.value = false;
  }
};
</script>

<style scoped>
.page-wrap {
  max-width: 640px;
}

.desc {
  margin-top: 6px;
  color: #64748b;
}

.strength-box {
  margin: -6px 0 14px;
  padding: 10px;
  border-radius: 10px;
  border: 1px dashed #bfdbfe;
  background: #f8fbff;
  color: #475569;
}

.strength-box small {
  display: block;
  margin-top: 6px;
  color: #64748b;
}

.actions {
  margin-top: 4px;
}
</style>
