<template>
  <el-config-provider :locale="elementLocale">
    <router-view />
  </el-config-provider>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import zhCn from 'element-plus/es/locale/lang/zh-cn';
import en from 'element-plus/es/locale/lang/en';
import { storeToRefs } from 'pinia';
import { useAppStore } from './stores/app';

const appStore = useAppStore();
const { language } = storeToRefs(appStore);

const elementLocale = computed(() => (language.value === 'zh-CN' ? zhCn : en));
</script>
