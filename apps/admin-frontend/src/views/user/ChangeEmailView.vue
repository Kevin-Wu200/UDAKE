<template>
  <div class="page-card page-wrap">
    <h2>修改邮箱</h2>
    <p class="desc">请输入新邮箱并完成验证码验证，系统会向旧邮箱发送变更通知。</p>

    <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent>
      <el-form-item label="新邮箱" prop="newEmail">
        <el-input v-model="form.newEmail" placeholder="请输入新邮箱" />
      </el-form-item>

      <el-form-item label="当前密码" prop="currentPassword">
        <el-input
          v-model="form.currentPassword"
          type="password"
          show-password
          placeholder="请输入当前密码"
        />
      </el-form-item>

      <el-form-item label="验证码" prop="code">
        <div class="code-row">
          <el-input v-model="form.code" placeholder="请输入验证码" maxlength="6" />
          <el-button :disabled="countdown > 0 || sendingCode" @click="onSendCode">
            {{ countdown > 0 ? `${countdown}s` : '发送验证码' }}
          </el-button>
        </div>
      </el-form-item>

      <div class="actions">
        <el-button type="primary" :loading="submitting" @click="onSubmit">确认修改</el-button>
      </div>
    </el-form>
  </div>
</template>

<script setup lang="ts">
import type { FormInstance, FormRules } from 'element-plus';
import { onBeforeUnmount, reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { useAuthStore } from '../../stores/auth';
import { sendChangeEmailCode, verifyChangeEmailCode } from '../../services/userAuthApi';

interface EmailForm {
  newEmail: string;
  currentPassword: string;
  code: string;
}

const authStore = useAuthStore();
const formRef = ref<FormInstance>();
const submitting = ref(false);
const sendingCode = ref(false);
const countdown = ref(0);
let countdownTimer: number | null = null;

const form = reactive<EmailForm>({
  newEmail: '',
  currentPassword: '',
  code: ''
});

const rules: FormRules<EmailForm> = {
  newEmail: [
    { required: true, message: '请输入新邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: ['blur', 'change'] }
  ],
  currentPassword: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  code: [{ required: true, message: '请输入验证码', trigger: 'blur' }]
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
    await formRef.value.validateField(['newEmail', 'currentPassword']);
    sendingCode.value = true;
    await sendChangeEmailCode(form.newEmail, form.currentPassword);
    startCountdown(600);
    ElMessage.success('验证码已发送，请查收新邮箱');
  } catch {
    // 错误由拦截器提示
  } finally {
    sendingCode.value = false;
  }
};

const onSubmit = async () => {
  if (!formRef.value) {
    return;
  }

  try {
    await formRef.value.validate();
    submitting.value = true;
    await verifyChangeEmailCode(form.code);

    const currentUser = authStore.user;
    if (currentUser) {
      authStore.setUser({
        ...currentUser,
        email: form.newEmail.trim().toLowerCase()
      });
    }

    ElMessage.success('邮箱修改成功，旧邮箱已收到通知');
    form.currentPassword = '';
    form.code = '';
    countdown.value = 0;
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
.page-wrap {
  max-width: 640px;
}

.desc {
  margin-top: 6px;
  color: #64748b;
}

.code-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 10px;
  width: 100%;
}

.actions {
  margin-top: 8px;
}

@media (max-width: 640px) {
  .code-row {
    grid-template-columns: 1fr;
  }
}
</style>
