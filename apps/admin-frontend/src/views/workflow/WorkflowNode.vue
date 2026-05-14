<template>
  <div class="workflow-node" :class="[{ disabled: !data.enabled }, `kind-${data.kind}`]" :style="nodeStyle">
    <Handle id="in" type="target" :position="Position.Left" class="handle" />
    <header class="node-header">
      <span class="kind-tag">{{ kindText }}</span>
      <span class="node-type">{{ data.nodeType }}</span>
    </header>
    <div class="node-title">{{ data.label }}</div>
    <div class="node-desc">{{ data.description || t('noDescription') }}</div>
    <Handle id="out" type="source" :position="Position.Right" class="handle" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { Handle, Position } from '@vue-flow/core';
import type { NodeProps } from '@vue-flow/core';
import { KIND_ACCENT, getKindText } from './workflowCanvas';
import type { WorkflowCanvasNodeData } from './workflowCanvas';
import { useI18nText } from '../../i18n/useI18n';

const { t } = useI18nText();
const props = defineProps<NodeProps<WorkflowCanvasNodeData>>();

const kindText = computed(() => getKindText(props.data.kind, t));
const nodeStyle = computed(() => ({
  '--accent-color': KIND_ACCENT[props.data.kind]
}));
</script>

<style scoped>
.workflow-node {
  width: 220px;
  border-radius: 12px;
  border: 1px solid #d7dee9;
  padding: 10px;
  background: #ffffff;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.08);
  position: relative;
}

.workflow-node::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  border-radius: 12px 0 0 12px;
  background: var(--accent-color);
}

.workflow-node.disabled {
  opacity: 0.55;
}

.node-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.kind-tag {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--accent-color) 16%, white);
  color: var(--accent-color);
  font-weight: 600;
}

.node-type {
  font-size: 11px;
  color: #64748b;
}

.node-title {
  margin-top: 8px;
  color: #0f172a;
  font-weight: 600;
  font-size: 14px;
}

.node-desc {
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
  line-height: 1.35;
}

.handle {
  width: 10px;
  height: 10px;
  background: var(--accent-color);
  border: 2px solid #fff;
}
</style>
