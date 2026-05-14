<template>
  <div class="forgot-page page-card">
    <h2>{{ t('forgotPassword') }}</h2>
    <p class="desc">{{ t('forgotPasswordDescription') }}</p>

    <el-steps :active="step" finish-status="success" class="steps">
      <el-step :title="t('stepEnterEmailAndKey')" />
      <el-step :title="t('stepEnterVerifyCode')" />
      <el-step :title="t('stepSetNewPassword')" />
      <el-step :title="t('stepSubmitReset')" />
    </el-steps>

    <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent>
      <div v-if="step === 0" class="stage">
        <el-form-item :label="t('email')" prop="email">
          <el-input v-model="form.email" :placeholder="t('enterEmail')" />
        </el-form-item>
        <el-form-item :label="t('productKey')" prop="productKey">
          <el-input v-model="form.productKey" :placeholder="t('enterProductKey')" />
        </el-form-item>
        <div class="actions">
          <el-button type="primary" :loading="sendingCode" @click="onSendCode">{{ t('sendCode') }}</el-button>
          <el-button @click="router.push('/user/login')">{{ t('backToLogin') }}</el-button>
        </div>
      </div>

      <div v-if="step === 1" class="stage">
        <el-alert :title="t('verificationCodeSentPrompt')" type="success" :closable="false" />
        <el-form-item :label="t('verificationCode')" prop="code" class="code-item">
          <div class="code-row">
            <el-input v-model="form.code" maxlength="6" :placeholder="t('enterCode')" />
            <el-button :disabled="countdown > 0 || sendingCode" @click="onSendCode">
              {{ countdown > 0 ? `${countdown}s` : t('resendCode') }}
            </el-button>
          </div>
        </el-form-item>
        <div class="actions">
          <el-button @click="step = 0">{{ t('previousStep') }}</el-button>
          <el-button type="primary" @click="goToPasswordStep">{{ t('nextStep') }}</el-button>
        </div>
      </div>

      <div v-if="step === 2" class="stage">
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
          <el-input
            v-model="form.confirmPassword"
            type="password"
            show-password
            :placeholder="t('enterConfirmPassword')"
          />
        </el-form-item>

        <div class="actions">
          <el-button @click="step = 1">{{ t('previousStep') }}</el-button>
          <el-button type="primary" @click="goToSubmitStep">{{ t('nextStep') }}</el-button>
        </div>
      </div>

      <div v-if="step === 3" class="stage">
        <el-descriptions border :column="1">
          <el-descriptions-item :label="t('email')">{{ form.email }}</el-descriptions-item>
          <el-descriptions-item :label="t('productKey')">{{ form.productKey }}</el-descriptions-item>
          <el-descriptions-item :label="t('verificationCode')">{{ form.code }}</el-descriptions-item>
          <el-descriptions-item :label="t('newPassword')">{{ t('passwordSet') }}</el-descriptions-item>
        </el-descriptions>
        <div class="actions">
          <el-button @click="step = 2">{{ t('previousStep') }}</el-button>
          <el-button type="primary" :loading="submitting" @click="onSubmitReset">{{ t('confirmReset') }}</el-button>
        </div>
      </div>
    </el-form>
  </div>
</template>

<script setup lang="ts">
import type { FormInstance, FormRules } from 'element-plus';
import { computed, onBeforeUnmount, reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { useRouter } from 'vue-router';
import { resetPasswordByCode, sendResetPasswordCode } from '../../services/userAuthApi';
import { evaluatePasswordStrength } from '../../utils/auth';
import { useI18nText } from '../../i18n/useI18n';

const { t } = useI18nText();

interface ResetForm {
  email: string;
  productKey: string;
  code: string;
  newPassword: string;
  confirmPassword: string;
}

const router = useRouter();
const formRef = ref<FormInstance>();

const step = ref(0);
const submitting = ref(false);
const sendingCode = ref(false);
const countdown = ref(0);
let countdownTimer: number | null = null;

const form = reactive<ResetForm>({
  email: '',
  productKey: '',
  code: '',
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

const rules: FormRules<ResetForm> = {
  email: [
    { required: true, message: t('enterEmail'), trigger: 'blur' },
    { type: 'email', message: t('invalidEmail'), trigger: ['blur', 'change'] }
  ],
  productKey: [{ required: true, message: t('enterProductKey'), trigger: 'blur' }],
  code: [{ required: true, message: t('enterCode'), trigger: 'blur' }],
  newPassword: [
    { required: true, message: t('enterNewPassword'), trigger: 'blur' },
    { validator: validatePasswordStrength, trigger: 'blur' }
  ],
  confirmPassword: [{ validator: validateConfirmPassword, trigger: 'blur' }]
};

const startCountdown = (seconds: number) => {
  countdown.value = seconds;
  if (countdownTimer !== null) {
    window.clearInterval(countdownTimer);
  }

  countdownTimer = window.setInterval(() => {
    countdown.value -= 1;
    if (countdown.value <= 0 && countdownTimer !== null) {
      window.clearInterval(countdownTimer);
      countdownTimer = null;
      countdown.value = 0;
    }
  }, 1000);
};

const onSendCode = async () => {
  if (!formRef.value) {
    return;
  }

  try {
    await formRef.value.validateField(['email', 'productKey']);
    sendingCode.value = true;
    await sendResetPasswordCode(form.email, form.productKey);
    startCountdown(600);
    step.value = 1;
    ElMessage.success(t('codeSentSuccessfully'));
  } catch {
    // 错误由拦截器提示
  } finally {
    sendingCode.value = false;
  }
};

const goToPasswordStep = async () => {
  if (!formRef.value) {
    return;
  }

  try {
    await formRef.value.validateField('code');
    step.value = 2;
  } catch {
    // 错误由表单提示
  }
};

const goToSubmitStep = async () => {
  if (!formRef.value) {
    return;
  }

  try {
    await formRef.value.validateField(['newPassword', 'confirmPassword']);
    step.value = 3;
  } catch {
    // 错误由表单提示
  }
};

const onSubmitReset = async () => {
  try {
    submitting.value = true;
    await resetPasswordByCode(form.email, form.code, form.newPassword, form.confirmPassword);
    ElMessage.success(t('passwordResetSuccess'));
    await router.replace('/user/login');
  } catch {
    // 错误由拦截器提示
  } finally {
    submitting.value = false;
  }
};

onBeforeUnmount(() => {
  if (countdownTimer !== null) {
    window.clearInterval(countdownTimer);
  }
});
</script>

<style scoped>
.forgot-page {
  max-width: 840px;
  margin: 0 auto;
}

.desc {
  margin-top: 6px;
  color: #64748b;
}

.steps {
  margin: 20px 0 24px;
}

.stage {
  display: grid;
  gap: 8px;
}

.code-item {
  margin-top: 8px;
}

.code-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 10px;
  width: 100%;
}

.strength-box {
  padding: 10px;
  border-radius: 10px;
  background: #f8fbff;
  border: 1px dashed #bfdbfe;
  color: #475569;
}

.strength-box small {
  display: block;
  margin-top: 6px;
  color: #64748b;
}

.actions {
  margin-top: 10px;
  display: flex;
  gap: 8px;
}

@media (max-width: 640px) {
  .code-row {
    grid-template-columns: 1fr;
  }
}
</style>
