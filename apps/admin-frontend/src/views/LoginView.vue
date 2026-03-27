<template>
  <div class="login-page">
    <div class="login-panel">
      <h1>{{ t('appTitle') }}</h1>
      <p class="sub-title">管理员后台登录</p>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent>
        <el-form-item :label="t('username')" prop="username">
          <el-input v-model="form.username" :placeholder="t('username')" />
        </el-form-item>
        <el-form-item :label="t('password')" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            :placeholder="t('password')"
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
import { reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '../stores/auth';
import { loginApi } from '../services/mockApi';
import { useI18nText } from '../i18n/useI18n';

interface LoginForm {
  username: string;
  password: string;
  rememberPassword: boolean;
}

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();
const { t } = useI18nText();

const formRef = ref<FormInstance>();
const submitting = ref(false);
const rememberedName = localStorage.getItem('admin_remember_name') ?? '';

const form = reactive<LoginForm>({
  username: rememberedName,
  password: '',
  rememberPassword: Boolean(rememberedName)
});

const rules: FormRules<LoginForm> = {
  username: [{ required: true, message: t('requiredUsername'), trigger: 'blur' }],
  password: [{ required: true, message: t('requiredPassword'), trigger: 'blur' }]
};

const onSubmit = async () => {
  if (!formRef.value) {
    return;
  }

  try {
    await formRef.value.validate();
    submitting.value = true;
    const res = await loginApi(form.username, form.password);
    authStore.login(form.username, res.accessToken);

    if (form.rememberPassword) {
      localStorage.setItem('admin_remember_name', form.username);
    } else {
      localStorage.removeItem('admin_remember_name');
    }

    ElMessage.success(t('loginSuccess'));
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/dashboard';
    router.push(redirect);
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
