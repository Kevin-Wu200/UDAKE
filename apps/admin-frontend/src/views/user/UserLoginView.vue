<template>
  <div class="user-login-page">
    <div class="panel">
      <h1>用户登录</h1>
      <p class="subtitle">支持自动登录、记住密码与Token自动刷新</p>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="请输入邮箱" />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            placeholder="请输入密码"
            @keyup.enter="onSubmit"
          />
        </el-form-item>

        <div class="row">
          <el-checkbox v-model="form.rememberPassword">记住密码</el-checkbox>
          <el-link type="primary" @click="router.push('/user/forgot-password')">找回密码</el-link>
        </div>

        <el-button type="primary" class="submit" :loading="submitting" @click="onSubmit">登录</el-button>

        <div class="footer-line">
          还没有账号？
          <el-link type="primary" @click="router.push('/user/register')">立即注册</el-link>
        </div>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { FormInstance, FormRules } from 'element-plus';
import { reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '../../stores/auth';
import { loginUser } from '../../services/userAuthApi';
import { decodeRememberPassword, encodeRememberPassword } from '../../utils/auth';

interface LoginForm {
  email: string;
  password: string;
  rememberPassword: boolean;
}

const REMEMBER_EMAIL_KEY = 'user_remember_email';
const REMEMBER_PASSWORD_KEY = 'user_remember_password';

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();

const rememberedEmail = localStorage.getItem(REMEMBER_EMAIL_KEY) ?? '';
const rememberedPasswordRaw = localStorage.getItem(REMEMBER_PASSWORD_KEY) ?? '';

const formRef = ref<FormInstance>();
const submitting = ref(false);
const form = reactive<LoginForm>({
  email: rememberedEmail,
  password: decodeRememberPassword(rememberedPasswordRaw),
  rememberPassword: Boolean(rememberedEmail && rememberedPasswordRaw)
});

const rules: FormRules<LoginForm> = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: ['blur', 'change'] }
  ],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
};

const onSubmit = async () => {
  if (!formRef.value) {
    return;
  }

  try {
    await formRef.value.validate();
    submitting.value = true;

    const session = await loginUser(form.email, form.password);
    authStore.applyUserSession(session);

    if (form.rememberPassword) {
      localStorage.setItem(REMEMBER_EMAIL_KEY, form.email.trim());
      localStorage.setItem(REMEMBER_PASSWORD_KEY, encodeRememberPassword(form.password));
    } else {
      localStorage.removeItem(REMEMBER_EMAIL_KEY);
      localStorage.removeItem(REMEMBER_PASSWORD_KEY);
    }

    ElMessage.success('登录成功');
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/user/devices';
    await router.replace(redirect);
  } catch {
    // 统一错误提示由 HTTP 拦截器处理
  } finally {
    submitting.value = false;
  }
};
</script>

<style scoped>
.user-login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background:
    radial-gradient(circle at 15% 15%, rgb(34 197 94 / 24%) 0, transparent 35%),
    radial-gradient(circle at 84% 6%, rgb(14 165 233 / 22%) 0, transparent 30%),
    #f8fafc;
}

.panel {
  width: min(430px, calc(100vw - 24px));
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

.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 6px 0 16px;
}

.submit {
  width: 100%;
}

.footer-line {
  margin-top: 14px;
  text-align: center;
  color: #475569;
}
</style>
