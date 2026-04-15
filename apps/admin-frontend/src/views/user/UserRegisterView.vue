<template>
  <div class="register-page">
    <div class="panel">
      <h1>用户注册</h1>
      <p class="subtitle">请输入邮箱、密码和产品密钥，完成验证码验证后即可开通账号。</p>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="请输入邮箱" />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password placeholder="请输入密码" />
        </el-form-item>

        <div class="strength-box">
          <div class="strength-title">
            密码强度：
            <span :style="{ color: passwordStrength.color }">{{ passwordStrength.label }}</span>
          </div>
          <el-progress :percentage="passwordStrength.score" :stroke-width="8" :color="passwordStrength.color" />
          <div class="strength-requirements">要求：至少8位，包含大小写字母和数字</div>
        </div>

        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            show-password
            placeholder="请再次输入密码"
          />
        </el-form-item>

        <el-form-item label="产品密钥" prop="productKey">
          <el-input
            v-model="form.productKey"
            placeholder="例如：ABC-1234-5678-9XYZ"
            @input="onProductKeyInput"
            @blur="() => onValidateProductKey(true)"
          />
        </el-form-item>

        <div class="key-status" :class="{ valid: keyValidation.valid, invalid: keyValidation.valid === false }">
          <span v-if="validating">密钥状态：校验中...</span>
          <span v-else-if="keyValidation.valid === true">
            密钥状态：有效（{{ keyValidation.typeLabel || keyValidation.type || '已校验' }}）
          </span>
          <span v-else-if="keyValidation.valid === false">密钥状态：{{ keyValidation.message || '密钥无效' }}</span>
          <span v-else>密钥状态：待校验</span>
        </div>

        <el-form-item label="邮箱验证码" prop="code">
          <div class="code-row">
            <el-input v-model="form.code" placeholder="请输入6位验证码" maxlength="6" />
            <el-button :disabled="countdown > 0 || codeSending" @click="onSendCode">
              {{ countdown > 0 ? `${countdown}s 后重发` : '发送验证码' }}
            </el-button>
          </div>
        </el-form-item>

        <el-button type="primary" class="submit" :loading="submitting" @click="onSubmit">
          完成注册
        </el-button>

        <div class="footer-line">
          已有账号？
          <el-link type="primary" @click="router.push('/user/login')">去登录</el-link>
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
    callback(new Error('请确认密码'));
    return;
  }
  if (value !== form.password) {
    callback(new Error('两次密码输入不一致'));
    return;
  }
  callback();
};

const validatePasswordStrength = (_rule: unknown, value: string, callback: (error?: Error) => void) => {
  const strength = evaluatePasswordStrength(value);
  if (strength.level === 'weak') {
    callback(new Error('密码强度不足，请至少8位并包含大小写字母和数字'));
    return;
  }
  callback();
};

const rules: FormRules<RegisterForm> = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: ['blur', 'change'] }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { validator: validatePasswordStrength, trigger: 'blur' }
  ],
  confirmPassword: [{ validator: validateConfirmPassword, trigger: 'blur' }],
  productKey: [{ required: true, message: '请输入产品密钥', trigger: 'blur' }],
  code: [{ required: true, message: '请输入验证码', trigger: 'blur' }]
};

function keyTypeLabel(keyType: string): string {
  switch (keyType) {
    case 'personal_standard':
      return '个人标准版';
    case 'enterprise_standard':
      return '企业标准版';
    case 'personal_trial':
      return '个人试用版';
    case 'enterprise_trial':
      return '企业试用版';
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
    keyValidation.message = error instanceof Error ? error.message : '密钥验证失败，请稍后重试';
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
    ElMessage.error(keyValidation.message || '产品密钥无效');
    return;
  }

  try {
    await formRef.value.validateField(['email', 'password', 'confirmPassword', 'productKey']);
    codeSending.value = true;
    await registerUser(form.email, form.password, form.productKey);
    codeRequested.value = true;
    startCountdown(60);
    ElMessage.success('验证码已发送，请查收邮箱');
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
      ElMessage.warning('请先发送验证码');
      return;
    }

    submitting.value = true;
    await verifyRegisterCode(form.email, form.code);

    const session = await loginUser(form.email, form.password);
    authStore.applyUserSession(session);
    ElMessage.success('注册成功，已自动登录');
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
