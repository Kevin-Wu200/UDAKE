<template>
  <div class="page-card page-wrap">
    <h2>修改密码</h2>
    <p class="desc">新密码不能与最近5次密码重复。修改后将自动退出，需要重新登录。</p>

    <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent>
      <el-form-item label="旧密码" prop="oldPassword">
        <el-input v-model="form.oldPassword" type="password" show-password placeholder="请输入旧密码" />
      </el-form-item>

      <el-form-item label="新密码" prop="newPassword">
        <el-input v-model="form.newPassword" type="password" show-password placeholder="请输入新密码" />
      </el-form-item>

      <div class="strength-box">
        <div>
          密码强度：
          <span :style="{ color: passwordStrength.color }">{{ passwordStrength.label }}</span>
        </div>
        <el-progress :percentage="passwordStrength.score" :stroke-width="8" :color="passwordStrength.color" />
        <small>强度要求：至少8位，包含大小写字母和数字</small>
      </div>

      <el-form-item label="确认新密码" prop="confirmPassword">
        <el-input v-model="form.confirmPassword" type="password" show-password placeholder="请再次输入新密码" />
      </el-form-item>

      <div class="actions">
        <el-button type="primary" :loading="submitting" @click="onSubmit">确认修改</el-button>
      </div>
    </el-form>
  </div>
</template>

<script setup lang="ts">
import type { FormInstance, FormRules } from 'element-plus';
import { computed, reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { useRouter } from 'vue-router';
import { useAuthStore } from '../../stores/auth';
import { changePassword } from '../../services/userAuthApi';
import { evaluatePasswordStrength } from '../../utils/auth';

interface PasswordForm {
  oldPassword: string;
  newPassword: string;
  confirmPassword: string;
}

const router = useRouter();
const authStore = useAuthStore();
const formRef = ref<FormInstance>();
const submitting = ref(false);

const form = reactive<PasswordForm>({
  oldPassword: '',
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

const rules: FormRules<PasswordForm> = {
  oldPassword: [{ required: true, message: '请输入旧密码', trigger: 'blur' }],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { validator: validatePasswordStrength, trigger: 'blur' }
  ],
  confirmPassword: [{ validator: validateConfirmPassword, trigger: 'blur' }]
};

const onSubmit = async () => {
  if (!formRef.value) {
    return;
  }

  try {
    await formRef.value.validate();
    submitting.value = true;
    await changePassword(form.oldPassword, form.newPassword, form.confirmPassword);

    ElMessage.success('密码修改成功，请重新登录');
    await authStore.logoutWithApi();
    await router.replace('/user/login');
  } catch {
    // 错误由拦截器提示
  } finally {
    submitting.value = false;
  }
};
</script>

<style scoped>
.page-wrap {
  max-width: 640px;
}

.desc {
  margin-top: 6px;
  color: #64748b;
}

.strength-box {
  margin: -6px 0 14px;
  padding: 10px;
  border-radius: 10px;
  border: 1px dashed #bfdbfe;
  background: #f8fbff;
  color: #475569;
}

.strength-box small {
  display: block;
  margin-top: 6px;
  color: #64748b;
}

.actions {
  margin-top: 4px;
}
</style>
