<template>
  <el-tag :type="tagType">{{ statusLabel }}</el-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{ status: 'pending' | 'approved' | 'rejected' | 'completed' }>();

const tagType = computed(() => {
  switch (props.status) {
    case 'pending': return 'info';
    case 'approved': return 'primary';
    case 'rejected': return 'danger';
    case 'completed': return 'success';
    default: return '';
  }
});

const statusLabel = computed(() => {
  switch (props.status) {
    case 'pending': return '待处理';
    case 'approved': return '已批准';
    case 'rejected': return '已拒绝';
    case 'completed': return '已完成';
    default: return props.status;
  }
});
</script>
