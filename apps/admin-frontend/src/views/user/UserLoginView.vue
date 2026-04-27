<template>
  <div class="user-login-page">
    <div class="panel">
       <div class="title-row">
        <h1>{{t('login.UserLogin')}}</h1>
        <el-select :model-value="appStore.language" style="width: 120px" @change="onLanguageChange">
          <el-option label="简体中文" value="zh-CN" />
          <el-option label="English" value="en-US" />
          <el-option label="日本語" value="ja-JP"/>
          <el-option label="繁體中文" value="zh-TW"/>
          <el-option label="한국어" value="ko-KR"/>
        </el-select>
        </div>
      <p class="subtitle">{{t('login.p')}}</p>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent>
        <el-form-item :label="t('login.Email')" prop="email">
          <el-input v-model="form.email" :placeholder="t('login.EnterEmail')" />
        </el-form-item>

        <el-form-item :label="t('login.Password')" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            :placeholder="t('login.EnterPassword')"
            @keyup.enter="onSubmit"
          />
        </el-form-item>

        <div class="row">
          <el-checkbox v-model="form.rememberPassword">{{t('login.RememberPassword')}}</el-checkbox>
          <el-link type="primary" @click="router.push('/user/forgot-password')">{{ t('login.FindPassword') }}</el-link>
        </div>

        <el-button type="primary" class="submit" :loading="submitting" @click="onSubmit">{{t('login.Login')}}</el-button>

        <div class="footer-line">
          {{t('login.NoAccount')}}
          <el-link type="primary" @click="router.push('/user/register')">{{t('login.Register')}}</el-link>
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
import { useAppStore } from '../../stores/app';
import type { AppLanguage } from '../../stores/app';
import { useI18nText_user } from '../../i18n/useI18n';

const { t } = useI18nText_user();

const appStore = useAppStore();
const onLanguageChange = (language: AppLanguage) => {
  appStore.setLanguage(language);
};

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
    { required: true, message: t('login.EnterEmail'), trigger: 'blur' },
    { type: 'email', message: t('login.IncorrectEmailFormat'), trigger: ['blur', 'change'] }
  ],
  password: [{ required: true, message: t('login.EnterPassword'), trigger: 'blur' }]
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

    ElMessage.success(t('login.success'));
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

.title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.title-row h1 {
  margin: 0;
}
</style>
