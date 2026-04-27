<template>
  <div class="register-page">
    <div class="panel">
      <div class="title-row">
        <h1>{{t('register.UserRegistration')}}</h1>
        <el-select :model-value="appStore.language" style="width: 120px" @change="onLanguageChange">
          <el-option label="简体中文" value="zh-CN" />
          <el-option label="English" value="en-US" />
          <el-option label="日本語" value="ja-JP"/>
          <el-option label="繁體中文" value="zh-TW"/>
          <el-option label="한국어" value="ko-KR"/>
        </el-select>
      </div>
      <p class="subtitle">{{t('register.p')}}</p>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent>
        <el-form-item :label="t('register.Email')" prop="email">
          <el-input v-model="form.email" :placeholder="t('register.EnterEmail')" />
        </el-form-item>

        <el-form-item :label="t('register.Password')" prop="password">
          <el-input v-model="form.password" type="password" show-password :placeholder="t('register.EnterPassword')" />
        </el-form-item>

        <div class="strength-box">
          <div class="strength-title">
            {{t('register.PasswordStrength')}}
            <span :style="{ color: passwordStrength.color }">{{ passwordStrength.label }}</span>
          </div>
          <el-progress :percentage="passwordStrength.score" :stroke-width="8" :color="passwordStrength.color" />
          <div class="strength-requirements">{{t('register.StrengthRequirement')}}</div>
        </div>

        <el-form-item :label="t('register.ConfirmPassWord')" prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            show-password
            :placeholder="t('register.EnterPasswordAgain')"
          />
        </el-form-item>

        <el-form-item :label="t('register.Key')" prop="productKey">
          <el-input
            v-model="form.productKey"
            :placeholder="t('register.Example')"
            @input="onProductKeyInput"
            @blur="() => onValidateProductKey(true)"
          />
        </el-form-item>

        <div class="key-status" :class="{ valid: keyValidation.valid, invalid: keyValidation.valid === false }">
          <span v-if="validating">{{t('register.KeyStatusVerification')}}</span>
          <span v-else-if="keyValidation.valid === true">
            {{t('register.KeyValid')}}（{{ keyValidation.typeLabel || keyValidation.type || t('register.Verified') }}）
          </span>
          <span v-else-if="keyValidation.valid === false">{{t('register.KeyStatus')}}{{ keyValidation.message || t('register.KeyInvalid') }}</span>
          <span v-else>{{t('register.KeyStatusToBeVerified')}}</span>
        </div>

        <el-form-item :label="t('register.EmailVerificationCode')" prop="code">
          <div class="code-row">
            <el-input v-model="form.code" :placeholder="t('register.EnterVerificationCode')" maxlength="6" />
            <el-button :disabled="countdown > 0 || codeSending" @click="onSendCode">
              {{ countdown > 0 ? t('register.ResendInSeconds', { countdown }) : t('register.SendVerificationCode') }}
            </el-button>
          </div>
        </el-form-item>

        <el-button type="primary" class="submit" :loading="submitting" @click="onSubmit">
          {{t('register.CompleteRegistration')}}
        </el-button>

        <div class="footer-line">
          {{t('register.HaveAccount')}}
          <el-link type="primary" @click="router.push('/user/login')">{{t('register.GoLogin')}}</el-link>
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
import { useAppStore } from '../../stores/app';
import type { AppLanguage } from '../../stores/app';
import { useI18nText_user } from '../../i18n/useI18n';

const { t } = useI18nText_user();

const appStore = useAppStore();
const onLanguageChange = (language: AppLanguage) => {
  appStore.setLanguage(language);
};

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
    callback(new Error(t('register.PleaseConfirmPassWord')));
    return;
  }
  if (value !== form.password) {
    callback(new Error(t('register.InconsistentPassword')));
    return;
  }
  callback();
};

const validatePasswordStrength = (_rule: unknown, value: string, callback: (error?: Error) => void) => {
  const strength = evaluatePasswordStrength(value);
  if (strength.level === 'weak') {
    callback(new Error(t('register.WeakPassword')));
    return;
  }
  callback();
};

const rules: FormRules<RegisterForm> = {
  email: [
    { required: true, message: t('register.EnterEmail'), trigger: 'blur' },
    { type: 'email', message: t('register.IncorrectEmailFormat'), trigger: ['blur', 'change'] }
  ],
  password: [
    { required: true, message: t('register.EnterPassword'), trigger: 'blur' },
    { validator: validatePasswordStrength, trigger: 'blur' }
  ],
  confirmPassword: [{ validator: validateConfirmPassword, trigger: 'blur' }],
  productKey: [{ required: true, message: t('register.PleaseEnterKey'), trigger: 'blur' }],
  code: [{ required: true, message: t('register.PleaseEnterVerificationCode'), trigger: 'blur' }]
};

function keyTypeLabel(keyType: string): string {
  switch (keyType) {
    case 'personal_standard':
      return t('register.PersonalStandard');
    case 'enterprise_standard':
      return t('register.EnterpriseStandard');
    case 'personal_trial':
      return t('register.PersonalTrial');
    case 'enterprise_trial':
      return t('register.EnterpriseTrial');
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
    keyValidation.message = error instanceof Error ? error.message : t('register.RetryKey');
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
  if (keyValidation.valid !== true) {
    ElMessage.error(keyValidation.message || t('register.ProductKeyInvalid'));
    return;
  }

  try {
    await formRef.value.validateField(['email', 'password', 'confirmPassword', 'productKey']);
    codeSending.value = true;
    await registerUser(form.email, form.password, form.productKey);
    codeRequested.value = true;
    startCountdown(60);
    ElMessage.success(t('register.VerificationCodeSend'));
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
      ElMessage.warning(t('register.PleaseSendVerificationCode'));
      return;
    }

    submitting.value = true;
    await verifyRegisterCode(form.email, form.code);

    const session = await loginUser(form.email, form.password);
    authStore.applyUserSession(session);
    ElMessage.success(t('register.Success'));
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

.title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.title-row h1 {
  margin: 0;
}

@media (max-width: 680px) {
  .code-row {
    grid-template-columns: 1fr;
  }
}
</style>
