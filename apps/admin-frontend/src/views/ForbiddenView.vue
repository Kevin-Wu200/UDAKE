<template>
  <div class="forbidden-page">
    <el-result icon="warning" title="403" :sub-title="t('forbiddenTitle')">
      <template #extra>
        <el-button type="primary" @click="router.push('/user/devices')">{{ t('backToUserCenter') }}</el-button>
        <el-button @click="router.push('/login/admin')">{{ t('goToAdminConsole') }}</el-button>
      </template>
    </el-result>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router';
import { useI18nText } from '../i18n/useI18n';

const { t } = useI18nText();
const router = useRouter();
</script>

<style scoped>
.forbidden-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background:
    radial-gradient(circle at 20% 20%, rgb(252 211 77 / 22%) 0, transparent 35%),
    radial-gradient(circle at 80% 5%, rgb(248 113 113 / 18%) 0, transparent 30%),
    #f8fafc;
}
</style>
