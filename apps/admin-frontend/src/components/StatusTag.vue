<template>
  <el-tag :type="tagType">{{ statusLabel }}</el-tag>
</template>

<script setup lang="ts">
import type { TagProps } from 'element-plus';
import { computed } from 'vue';
import { useI18nText } from '../i18n/useI18n';

const props = defineProps<{ status: 'pending' | 'approved' | 'rejected' | 'completed' }>();
const { tc } = useI18nText();

const tagType = computed<TagProps['type']>(() => {
  switch (props.status) {
    case 'pending': return 'info';
    case 'approved': return 'primary';
    case 'rejected': return 'danger';
    case 'completed': return 'success';
    default: return 'info';
  }
});

const statusLabel = computed(() => {
  switch (props.status) {
    case 'pending': return tc('pending');
    case 'approved': return tc('approved');
    case 'rejected': return tc('rejected');
    case 'completed': return tc('completed');
    default: return props.status;
  }
});
</script>
