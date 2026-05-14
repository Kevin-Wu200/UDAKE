<template>
  <div class="register-page">
    <div class="panel">
      <h1>{{ t('userRegister') }}</h1>
      <p class="subtitle">{{ t('registerDescription') }}</p>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent>
        <el-form-item :label="t('email')" prop="email">
          <el-input v-model="form.email" :placeholder="t('enterEmail')" />
        </el-form-item>

        <el-form-item :label="t('password')" prop="password">
          <el-input v-model="form.password" type="password" show-password :placeholder="t('enterPassword')" />
        </el-form-item>

        <div class="strength-box">
          <div class="strength-title">
            {{ t('passwordStrength') }}：
            <span :style="{ color: passwordStrength.color }">{{ passwordStrength.label }}</span>
          </div>
          <el-progress :percentage="passwordStrength.score" :stroke-width="8" :color="passwordStrength.color" />
          <div class="strength-requirements">{{ t('passwordRequirements') }}</div>
        </div>

        <el-form-item :label="t('confirmPassword')" prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            show-password
            :placeholder="t('enterConfirmPassword')"
          />
        </el-form-item>

        <el-form-item :label="t('productKey')" prop="productKey">
          <el-input
            v-model="form.productKey"
            :placeholder="t('productKeyExample')"
            @input="onProductKeyInput"
            @blur="() => onValidateProductKey(true)"
          />
        </el-form-item>

        <div class="key-status" :class="{ valid: keyValidation.valid, invalid: keyValidation.valid === false }">
          <span v-if="validating">{{ t('keyStatus') }}{{ t('keyValidating') }}</span>
          <span v-else-if="keyValidation.valid === true">
            {{ t('keyStatus') }}{{ t('keyValid') }}（{{ keyValidation.typeLabel || keyValidation.type || t('keyValid') }}）
          </span>
          <span v-else-if="keyValidation.valid === false">{{ t('keyStatus') }}{{ keyValidation.message || t('keyInvalid') }}</span>
          <span v-else>{{ t('keyStatus') }}{{ t('keyPendingValidation') }}</span>
        </div>

        <el-form-item :label="t('emailCode')" prop="code">
          <div class="code-row">
            <el-input v-model="form.code" :placeholder="t('enterCode')" maxlength="6" />
            <el-button :disabled="countdown > 0 || codeSending" @click="onSendCode">
              {{ countdown > 0 ? `${countdown}s` : t('sendCode') }}
            </el-button>
          </div>
        </el-form-item>

        <el-button type="primary" class="submit" :loading="submitting" @click="onSubmit">
          {{ t('completeRegistration') }}
        </el-button>

        <div class="footer-line">
          {{ t('hasAccountHint') }}
          <el-link type="primary" @click="router.push('/user/login')">{{ t('goToLogin') }}</el-link>
        </div>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { FormInstance, FormRules } from 'element-plus';
import { computed, onBeforeUnmount, reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { useRouter } from 'vue-router';
import { useAuthStore } from '../../stores/auth';
import { loginUser, registerUser, validateProductKey, verifyRegisterCode } from '../../services/userAuthApi';
import { evaluatePasswordStrength } from '../../utils/auth';
import { useI18nText } from '../../i18n/useI18n';

const { t } = useI18nText();

interface RegisterForm {
  email: string;
  password: string;
  confirmPassword: string;
  productKey: string;
  code: string;
}

interface KeyValidationState {
  valid: boolean | null;
  type: string;
  typeLabel: string;
  message: string;
}

const router = useRouter();
const authStore = useAuthStore();
const formRef = ref<FormInstance>();

const submitting = ref(false);
const codeSending = ref(false);
const validating = ref(false);
const countdown = ref(0);
const codeRequested = ref(false);
let countdownTimer: number | null = null;
let validateTimer: number | null = null;
let validateSeq = 0;

const form = reactive<RegisterForm>({
  email: '',
  password: '',
  confirmPassword: '',
  productKey: '',
  code: ''
});

const keyValidation = reactive<KeyValidationState>({
  valid: null,
  type: '',
  typeLabel: '',
  message: ''
});

const passwordStrength = computed(() => evaluatePasswordStrength(form.password));

const validateConfirmPassword = (_rule: unknown, value: string, callback: (error?: Error) => void) => {
  if (!value) {
    callback(new Error(t('confirmPassword')));
    return;
  }
  if (value !== form.password) {
    callback(new Error(t('passwordsDoNotMatch')));
    return;
  }
  callback();
};

const validatePasswordStrength = (_rule: unknown, value: string, callback: (error?: Error) => void) => {
  const strength = evaluatePasswordStrength(value);
  if (strength.level === 'weak') {
    callback(new Error(t('passwordStrengthRequirement')));
    return;
  }
  callback();
};

const rules: FormRules<RegisterForm> = {
  email: [
    { required: true, message: t('enterEmail'), trigger: 'blur' },
    { type: 'email', message: t('invalidEmail'), trigger: ['blur', 'change'] }
  ],
  password: [
    { required: true, message: t('enterPassword'), trigger: 'blur' },
    { validator: validatePasswordStrength, trigger: 'blur' }
  ],
  confirmPassword: [{ validator: validateConfirmPassword, trigger: 'blur' }],
  productKey: [{ required: true, message: t('enterProductKey'), trigger: 'blur' }],
  code: [{ required: true, message: t('enterCode'), trigger: 'blur' }]
};

function keyTypeLabel(keyType: string): string {
  switch (keyType) {
    case 'personal_standard':
      return t('personalStandard');
    case 'enterprise_standard':
      return t('enterpriseStandard');
    case 'personal_trial':
      return t('personalTrial');
    case 'enterprise_trial':
      return t('enterpriseTrial');
    default:
      return '';
  }
}

const resetKeyValidation = () => {
  keyValidation.valid = null;
  keyValidation.type = '';
  keyValidation.typeLabel = '';
  keyValidation.message = '';
};

const runValidateProductKey = async () => {
  const seq = ++validateSeq;
  const normalized = form.productKey.trim().toUpperCase();
  form.productKey = normalized;

  if (!normalized) {
    resetKeyValidation();
    return;
  }

  validating.value = true;
  try {
    const result = await validateProductKey(normalized);
    if (seq !== validateSeq) {
      return;
    }
    keyValidation.valid = result.valid;
    keyValidation.type = result.keyType;
    keyValidation.typeLabel = keyTypeLabel(result.keyType);
    keyValidation.message = result.message;
  } catch (error) {
    if (seq !== validateSeq) {
      return;
    }
    keyValidation.valid = false;
    keyValidation.type = '';
    keyValidation.typeLabel = '';
    keyValidation.message = error instanceof Error ? error.message : t('keyValidationFailed');
  } finally {
    if (seq === validateSeq) {
      validating.value = false;
    }
  }
};

const onValidateProductKey = async (immediate = false) => {
  if (validateTimer !== null) {
    window.clearTimeout(validateTimer);
    validateTimer = null;
  }
  if (immediate) {
    await runValidateProductKey();
    return;
  }
  validateTimer = window.setTimeout(() => {
    validateTimer = null;
    void runValidateProductKey();
  }, 500);
};

const onProductKeyInput = () => {
  void onValidateProductKey(false);
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

  await onValidateProductKey(true);

  try {
    await formRef.value.validateField(['email', 'password', 'confirmPassword', 'productKey']);
    codeSending.value = true;
    await registerUser(form.email, form.password, form.productKey);
    codeRequested.value = true;
    startCountdown(60);
    ElMessage.success(t('codeSent'));
  } catch {
    // 由拦截器展示错误
  } finally {
    codeSending.value = false;
  }
};

const onSubmit = async () => {
  if (!formRef.value) {
    return;
  }

  try {
    await formRef.value.validate();
    if (!codeRequested.value) {
      ElMessage.warning(t('pleaseSendCodeFirst'));
      return;
    }

    submitting.value = true;
    await verifyRegisterCode(form.email, form.code);

    const session = await loginUser(form.email, form.password);
    authStore.applyUserSession(session);
    ElMessage.success(t('registerSuccess'));
    await router.replace('/user/devices');
  } catch {
    // 由拦截器展示错误
  } finally {
    submitting.value = false;
  }
};

onBeforeUnmount(() => {
  if (countdownTimer !== null) {
    window.clearInterval(countdownTimer);
  }
  if (validateTimer !== null) {
    window.clearTimeout(validateTimer);
  }
});
</script>

<style scoped>
.register-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background:
    radial-gradient(circle at 18% 16%, rgb(59 130 246 / 18%) 0, transparent 30%),
    radial-gradient(circle at 78% 4%, rgb(16 185 129 / 20%) 0, transparent 32%),
    #f8fafc;
}

.panel {
  width: min(520px, calc(100vw - 24px));
  background: #fff;
  border: 1px solid #dbeafe;
  border-radius: 14px;
  padding: 24px;
  box-shadow: 0 18px 44px rgb(15 23 42 / 10%);
}

h1 {
  font-size: 28px;
  color: #0f172a;
}

.subtitle {
  margin: 8px 0 18px;
  color: #64748b;
}

.strength-box {
  margin: -6px 0 14px;
  padding: 10px;
  border: 1px dashed #dbeafe;
  border-radius: 10px;
  background: #f8fbff;
}

.strength-title {
  margin-bottom: 6px;
  font-size: 13px;
  color: #475569;
}

.strength-requirements {
  margin-top: 6px;
  font-size: 12px;
  color: #64748b;
}

.key-status {
  margin: -4px 0 12px;
  font-size: 13px;
  color: #64748b;
}

.key-status.valid {
  color: #16a34a;
}

.key-status.invalid {
  color: #dc2626;
}

.code-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 10px;
  width: 100%;
}

.submit {
  width: 100%;
  margin-top: 6px;
}

.footer-line {
  margin-top: 14px;
  text-align: center;
  color: #475569;
}

@media (max-width: 680px) {
  .code-row {
    grid-template-columns: 1fr;
  }
}
</style>
