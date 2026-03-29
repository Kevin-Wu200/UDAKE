<template>
  <BaseEdge :id="id" :path="path" :style="edgeStyle" :marker-end="markerEnd" />
  <EdgeLabelRenderer>
    <div
      v-if="edgeLabel"
      class="edge-label nodrag nopan"
      :style="{
        transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`
      }"
    >
      {{ edgeLabel }}
    </div>
  </EdgeLabelRenderer>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { BaseEdge, EdgeLabelRenderer, getBezierPath } from '@vue-flow/core';
import type { EdgeProps } from '@vue-flow/core';

const props = defineProps<EdgeProps>();

const [path, labelX, labelY] = getBezierPath(props);

const edgeLabel = computed(() => {
  const condition = props.data?.condition;
  if (typeof condition !== 'string' || !condition.trim() || condition === 'always') {
    return '';
  }
  return condition;
});

const edgeStyle = {
  strokeWidth: 2,
  stroke: '#64748b'
};
</script>

<style scoped>
.edge-label {
  position: absolute;
  background: #ffffff;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  font-size: 11px;
  color: #334155;
  padding: 2px 6px;
  pointer-events: none;
  max-width: 180px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
