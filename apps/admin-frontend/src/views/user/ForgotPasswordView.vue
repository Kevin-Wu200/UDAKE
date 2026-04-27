<template>
  <div class="forgot-page page-card" >   
    <div class="title-row">
      <h2>{{t('Fpassword.RetrievePassword')}}</h2>
      <el-select :model-value="appStore.language" style="width: 120px" @change="onLanguageChange">
        <el-option label="简体中文" value="zh-CN" />
        <el-option label="English" value="en-US" />
        <el-option label="日本語" value="ja-JP"/>
        <el-option label="繁體中文" value="zh-TW"/>
        <el-option label="한국어" value="ko-KR"/>
      </el-select>
    </div>
        
    <p class="desc">{{t('Fpassword.p')}}</p>

    <el-steps :active="step" finish-status="success" class="steps">
      <el-step :title="t('Fpassword.EnterEmailAndKey')" />
      <el-step :title="t('Fpassword.EnterVerificationCode')" />
      <el-step :title="t('Fpassword.SetNewPassword')" />
      <el-step :title="t('Fpassword.SubmitReset')" />
    </el-steps>

    <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent>
      <div v-if="step === 0" class="stage">
        <el-form-item :label="t('Fpassword.Email')" prop="email">
          <el-input v-model="form.email" :placeholder="t('Fpassword.EnterEmail')" />
        </el-form-item>
        <el-form-item :label="t('Fpassword.Key')" prop="productKey">
          <el-input v-model="form.productKey" :placeholder="t('Fpassword.EnterKey')" />
        </el-form-item>
        <div class="actions">
          <el-button type="primary" :loading="sendingCode" @click="onSendCode">{{t( 'Fpassword.SendVerificationCode')}}</el-button>
          <el-button @click="router.push('/user/login')">{{t('Fpassword.ReturnToLogin')}}</el-button>
        </div>
      </div>

      <div v-if="step === 1" class="stage">
        <el-alert :title="t('Fpassword.VerificationCodeSent')" type="success" :closable="false" />
        <el-form-item :label="t('Fpassword.VerificationCode')" prop="code" class="code-item">
          <div class="code-row">
            <el-input v-model="form.code" maxlength="6" :placeholder="t('Fpassword.PleaseEnterVerificationCode')" />
            <el-button :disabled="countdown > 0 || sendingCode" @click="onSendCode">
              {{ countdown > 0 ? `${countdown}s` : t('Fpassword.resent') }}
            </el-button>
          </div>
        </el-form-item>
        <div class="actions">
          <el-button @click="step = 0">{{t('Fpassword.PreviousStep')}}</el-button>
          <el-button type="primary" @click="goToPasswordStep">{{t('Fpassword.NextStep')}}</el-button>
        </div>
      </div>

      <div v-if="step === 2" class="stage">
        <el-form-item :label="t('Fpassword.NewPassword')" prop="newPassword">
          <el-input v-model="form.newPassword" type="password" show-password :placeholder="t('Fpassword.EnterNewPassword')" />
        </el-form-item>

        <div class="strength-box">
          <div>
            {{t('Fpassword.PasswordStrength')}}
            <span :style="{ color: passwordStrength.color }">{{ passwordStrength.label }}</span>
          </div>
          <el-progress :percentage="passwordStrength.score" :stroke-width="8" :color="passwordStrength.color" />
          <small>{{t( 'Fpassword.StrengthRequirement')}}</small>
        </div>

        <el-form-item :label="t('Fpassword.ConfirmNewPassword')" prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            show-password
            :placeholder="t('Fpassword.EnterNewPasswordAgain')"
          />
        </el-form-item>

        <div class="actions">
          <el-button @click="step = 1">{{t('Fpassword.PreviousStep')}}</el-button>
          <el-button type="primary" @click="goToSubmitStep">{{t('Fpassword.NextStep')}}</el-button>
        </div>
      </div>

      <div v-if="step === 3" class="stage">
        <el-descriptions border :column="1">
          <el-descriptions-item :label="t('Fpassword.Email')">{{ form.email }}</el-descriptions-item>
          <el-descriptions-item :label="t('Fpassword.Key')">{{ form.productKey }}</el-descriptions-item>
          <el-descriptions-item :label="t('Fpassword.VerificationCode')">{{ form.code }}</el-descriptions-item>
          <el-descriptions-item :label="t('Fpassword.NewPassword')">{{t('Fpassword.Set')}}</el-descriptions-item>
        </el-descriptions>
        <div class="actions">
          <el-button @click="step = 2">{{t('Fpassword.PreviousStep')}}</el-button>
          <el-button type="primary" :loading="submitting" @click="onSubmitReset">{{t('Fpassword.ConfirmReset')}}</el-button>
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
import { useAppStore } from '../../stores/app';
import type { AppLanguage } from '../../stores/app';
import { useAuthStore } from '../../stores/auth';
import { useI18nText_user } from '../../i18n/useI18n';

const { t } = useI18nText_user();

const authStore = useAuthStore();
const appStore = useAppStore();
const onLanguageChange = (language: AppLanguage) => {
  appStore.setLanguage(language);
};

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
    callback(new Error(t('Fpassword.WeakPassword')));
    return;
  }
  callback();
};

const validateConfirmPassword = (_rule: unknown, value: string, callback: (error?: Error) => void) => {
  if (!value) {
    callback(new Error(t('Fpassword.EnterNewPasswordAgain')));
    return;
  }
  if (value !== form.newPassword) {
    callback(new Error(t('Fpassword.InconsistentPassword')));
    return;
  }
  callback();
};

const rules: FormRules<ResetForm> = {
  email: [
    { required: true, message: t('Fpassword.PleaseEnterEmail'), trigger: 'blur' },
    { type: 'email', message: t('Fpassword.IncorrectEmailFormat'), trigger: ['blur', 'change'] }
  ],
  productKey: [{ required: true, message: t('Fpassword.EnterKey'), trigger: 'blur' }],
  code: [{ required: true, message: t('Fpassword.PleaseEnterVerificationCode'), trigger: 'blur' }],
  newPassword: [
    { required: true, message: t('Fpassword.EnterNewPassword'), trigger: 'blur' },
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
    ElMessage.success(t('Fpassword.SendVerificationCodeSuccess'));
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
    ElMessage.success(t('Fpassword.Success'));
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
  width: 80%;
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

.title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.title-row h2 {
  margin: 0;
}


@media (max-width: 640px) {
  .code-row {
    grid-template-columns: 1fr;
  }
}
</style>
