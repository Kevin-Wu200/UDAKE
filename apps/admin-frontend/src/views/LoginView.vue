<template>
  <div class="login-page">
    <div class="login-panel">
      <div style="display: flex; align-items: center;">
        <h1 style="width: 80%;">{{ t('appTitle') }}</h1>
        <el-select :model-value="appStore.language" style="width: 120px;" @change="onLanguageChange">
          <el-option label="简体中文" value="zh-CN" />
          <el-option label="English" value="en-US" />
          <el-option label="日本語" value="ja-JP"/>
          <el-option label="繁體中文" value="zh-TW"/>
          <el-option label="한국어" value="ko-KR"/>
        </el-select>
      </div>
      <p class="sub-title">{{ t('subTitle') }}</p>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent>
        <el-form-item :label="t('email')" prop="email">
          <el-input v-model="form.email" :placeholder="t('email')" />
        </el-form-item>
        <el-form-item :label="t('password')" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            :placeholder="t('password')"
            @keyup.enter="onSubmit"
          />
        </el-form-item>
        <div class="row">
          <el-checkbox v-model="form.rememberPassword">{{ t('rememberPassword') }}</el-checkbox>
        </div>
        <el-button type="primary" class="submit" :loading="submitting" @click="onSubmit">
          {{ t('login') }}
        </el-button>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { FormInstance, FormRules } from 'element-plus';
import type { AppLanguage } from '../stores/app';
import { reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { useRoute, useRouter } from 'vue-router';
import { isAdminRole, useAuthStore } from '../stores/auth';
import { loginUser } from '../services/userAuthApi';
import { useI18nText } from '../i18n/useI18n';
import { decodeRememberPassword, encodeRememberPassword } from '../utils/auth';
import { useAppStore } from '../stores/app';

const appStore = useAppStore();

interface LoginForm {
  email: string;
  password: string;
  rememberPassword: boolean;
}

const PASSWORD_PATTERN = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$/;
const REMEMBER_EMAIL_KEY = 'admin_remember_email';
const REMEMBER_PASSWORD_KEY = 'admin_remember_password';

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();
const { t } = useI18nText();

const formRef = ref<FormInstance>();
const submitting = ref(false);
const rememberedEmail = localStorage.getItem(REMEMBER_EMAIL_KEY) ?? '';
const rememberedPasswordRaw = localStorage.getItem(REMEMBER_PASSWORD_KEY) ?? '';

const onLanguageChange = (language: AppLanguage) => {
  appStore.setLanguage(language);
};

const form = reactive<LoginForm>({
  email: rememberedEmail,
  password: decodeRememberPassword(rememberedPasswordRaw),
  rememberPassword: Boolean(rememberedEmail && rememberedPasswordRaw)
});

const rules: FormRules<LoginForm> = {
  email: [
    { required: true, message: t('requiredEmail'), trigger: 'blur' },
    { type: 'email', message: t('invalidEmail'), trigger: ['blur', 'change'] }
  ],
  password: [
    { required: true, message: t('requiredPassword'), trigger: 'blur' },
    {
      validator: (_rule, value: string, callback) => {
        if (!value || PASSWORD_PATTERN.test(value)) {
          callback();
          return;
        }
        callback(new Error(t('invalidPasswordStrength')));
      },
      trigger: ['blur', 'change']
    }
  ]
};

const onSubmit = async () => {
  if (!formRef.value) {
    return;
  }

  try {
    await formRef.value.validate();
    submitting.value = true;
    const session = await loginUser(form.email.trim().toLowerCase(), form.password);
    if (!isAdminRole(session.user.role)) {
      throw new Error(t('adminRoleRequired'));
    }
    authStore.applyUserSession(session);

    if (form.rememberPassword) {
      localStorage.setItem(REMEMBER_EMAIL_KEY, form.email.trim().toLowerCase());
      localStorage.setItem(REMEMBER_PASSWORD_KEY, encodeRememberPassword(form.password));
    } else {
      localStorage.removeItem(REMEMBER_EMAIL_KEY);
      localStorage.removeItem(REMEMBER_PASSWORD_KEY);
    }

    ElMessage.success(t('loginSuccess'));
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/dashboard';
    await router.replace(redirect);
  } catch (error) {
    if (error instanceof Error) {
      ElMessage.error(error.message);
    }
  } finally {
    submitting.value = false;
  }
};
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background:
    radial-gradient(circle at 20% 20%, #e0f5f2 0, transparent 35%),
    radial-gradient(circle at 80% 0%, #bfe5ff 0, transparent 30%),
    #f7fbff;
}

.login-panel {
  width: min(420px, calc(100vw - 28px));
  padding: 28px;
  border-radius: 16px;
  background: #fff;
  border: 1px solid #d4e4ee;
  box-shadow: 0 16px 42px rgb(15 23 42 / 9%);
}

h1 {
  font-size: 28px;
  color: #0f172a;
}

.sub-title {
  margin: 8px 0 20px;
  color: #475569;
}

.row {
  margin: 8px 0 16px;
}

.submit {
  width: 100%;
}
</style>
