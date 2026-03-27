<template>
  <div class="forgot-page page-card">
    <h2>找回密码</h2>
    <p class="desc">按照步骤完成邮箱验证并重置密码，验证码10分钟内有效。</p>

    <el-steps :active="step" finish-status="success" class="steps">
      <el-step title="输入邮箱与密钥" />
      <el-step title="输入验证码" />
      <el-step title="设置新密码" />
      <el-step title="提交重置" />
    </el-steps>

    <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent>
      <div v-if="step === 0" class="stage">
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="请输入注册邮箱" />
        </el-form-item>
        <el-form-item label="产品密钥" prop="productKey">
          <el-input v-model="form.productKey" placeholder="请输入产品密钥" />
        </el-form-item>
        <div class="actions">
          <el-button type="primary" :loading="sendingCode" @click="onSendCode">发送验证码</el-button>
          <el-button @click="router.push('/user/login')">返回登录</el-button>
        </div>
      </div>

      <div v-if="step === 1" class="stage">
        <el-alert title="验证码已发送，请在10分钟内完成验证" type="success" :closable="false" />
        <el-form-item label="验证码" prop="code" class="code-item">
          <div class="code-row">
            <el-input v-model="form.code" maxlength="6" placeholder="请输入验证码" />
            <el-button :disabled="countdown > 0 || sendingCode" @click="onSendCode">
              {{ countdown > 0 ? `${countdown}s` : '重新发送' }}
            </el-button>
          </div>
        </el-form-item>
        <div class="actions">
          <el-button @click="step = 0">上一步</el-button>
          <el-button type="primary" @click="goToPasswordStep">下一步</el-button>
        </div>
      </div>

      <div v-if="step === 2" class="stage">
        <el-form-item label="新密码" prop="newPassword">
          <el-input v-model="form.newPassword" type="password" show-password placeholder="请输入新密码" />
        </el-form-item>

        <div class="strength-box">
          <div>
            密码强度：
            <span :style="{ color: passwordStrength.color }">{{ passwordStrength.label }}</span>
          </div>
          <el-progress :percentage="passwordStrength.score" :stroke-width="8" :color="passwordStrength.color" />
          <small>要求：至少8位，且包含大小写字母和数字</small>
        </div>

        <el-form-item label="确认新密码" prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            show-password
            placeholder="请再次输入新密码"
          />
        </el-form-item>

        <div class="actions">
          <el-button @click="step = 1">上一步</el-button>
          <el-button type="primary" @click="goToSubmitStep">下一步</el-button>
        </div>
      </div>

      <div v-if="step === 3" class="stage">
        <el-descriptions border :column="1">
          <el-descriptions-item label="邮箱">{{ form.email }}</el-descriptions-item>
          <el-descriptions-item label="产品密钥">{{ form.productKey }}</el-descriptions-item>
          <el-descriptions-item label="验证码">{{ form.code }}</el-descriptions-item>
          <el-descriptions-item label="新密码">已设置</el-descriptions-item>
        </el-descriptions>
        <div class="actions">
          <el-button @click="step = 2">上一步</el-button>
          <el-button type="primary" :loading="submitting" @click="onSubmitReset">确认重置</el-button>
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
    callback(new Error('密码强度不足'));
    return;
  }
  callback();
};

const validateConfirmPassword = (_rule: unknown, value: string, callback: (error?: Error) => void) => {
  if (!value) {
    callback(new Error('请再次输入新密码'));
    return;
  }
  if (value !== form.newPassword) {
    callback(new Error('两次密码输入不一致'));
    return;
  }
  callback();
};

const rules: FormRules<ResetForm> = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: ['blur', 'change'] }
  ],
  productKey: [{ required: true, message: '请输入产品密钥', trigger: 'blur' }],
  code: [{ required: true, message: '请输入验证码', trigger: 'blur' }],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
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
    ElMessage.success('验证码发送成功');
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
    ElMessage.success('密码重置成功，请使用新密码登录');
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
