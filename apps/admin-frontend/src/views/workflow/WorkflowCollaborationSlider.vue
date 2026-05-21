<template>
  <div class="collaboration-slider-wrapper" :class="{ 'slider-visible': visible }">
    <div
      class="slider-backdrop"
      @click="close"
      @touchstart="onDragStart"
    />
    <div
      class="slider-panel"
      :class="[`slider-${position}`, { 'slider-dragging': isDragging }]"
      :style="panelStyle"
      @touchstart="onDragStart"
      @touchmove="onDragMove"
      @touchend="onDragEnd"
    >
      <div class="slider-handle" @mousedown="onDragStart">
        <span class="handle-bar" />
      </div>

      <header class="slider-header">
        <h3>{{ title }}</h3>
        <el-button size="small" text @click="close">✕</el-button>
      </header>

      <!-- 协作状态条 -->
      <div class="collaboration-status-bar">
        <div class="status-item">
          <span class="status-label">在线用户</span>
          <strong>{{ onlineCount }}</strong>
        </div>
        <div class="status-item">
          <span class="status-label">分支数</span>
          <el-tag :type="branchCount > 0 ? 'warning' : 'info'" size="small">{{ branchCount }}</el-tag>
        </div>
        <div class="status-item">
          <span class="status-label">锁定状态</span>
          <el-tag :type="isLocked ? 'danger' : 'success'" size="small">
            {{ isLocked ? `已锁定 (${lockHolder})` : '未锁定' }}
          </el-tag>
        </div>
      </div>

      <!-- 内容区域 -->
      <div class="slider-content">
        <slot name="default">
          <div class="placeholder-content">
            <p>协作面板内容区域</p>
          </div>
        </slot>
      </div>

      <!-- 底部操作区 -->
      <div class="slider-footer">
        <slot name="footer">
          <el-button size="small" @click="close">关闭</el-button>
        </slot>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';

interface Props {
  visible: boolean;
  position?: 'left' | 'right';
  title?: string;
  onlineCount?: number;
  branchCount?: number;
  isLocked?: boolean;
  lockHolder?: string;
}

const props = withDefaults(defineProps<Props>(), {
  position: 'right',
  title: '协作面板',
  onlineCount: 0,
  branchCount: 0,
  isLocked: false,
  lockHolder: '',
});

const emit = defineEmits<{
  close: [];
}>();

const isDragging = ref(false);
const dragOffset = ref(0);
const startX = ref(0);
const startOffset = ref(0);

const panelWidth = 380; // px

const panelStyle = computed(() => {
  if (props.position === 'right') {
    return {
      transform: isDragging.value
        ? `translateX(${dragOffset.value}px)`
        : props.visible
          ? 'translateX(0)'
          : `translateX(${panelWidth}px)`,
    };
  }
  return {
    transform: isDragging.value
      ? `translateX(${dragOffset.value}px)`
      : props.visible
        ? 'translateX(0)'
        : `translateX(-${panelWidth}px)`,
  };
});

function close() {
  emit('close');
}

function onDragStart(e: MouseEvent | TouchEvent) {
  isDragging.value = true;
  startX.value = 'touches' in e ? e.touches[0].clientX : e.clientX;
  startOffset.value = dragOffset.value;
}

function onDragMove(e: TouchEvent) {
  if (!isDragging.value) return;
  const currentX = e.touches[0].clientX;
  const diff = currentX - startX.value;
  if (props.position === 'right') {
    dragOffset.value = Math.max(0, Math.min(panelWidth, startOffset.value + diff));
  } else {
    dragOffset.value = Math.min(0, Math.max(-panelWidth, startOffset.value + diff));
  }
}

function onDragEnd() {
  isDragging.value = false;
  // 如果拖拽超过一半宽度则关闭
  if (Math.abs(dragOffset.value) > panelWidth / 2) {
    close();
    dragOffset.value = 0;
  } else {
    dragOffset.value = 0;
  }
}
</script>

<style scoped>
.collaboration-slider-wrapper {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 2000;
  pointer-events: none;
}

.collaboration-slider-wrapper.slider-visible {
  pointer-events: auto;
}

.slider-backdrop {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.2);
  opacity: 0;
  transition: opacity 300ms ease;
}

.slider-visible .slider-backdrop {
  opacity: 1;
}

.slider-panel {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 380px;
  max-width: 90vw;
  background: #fff;
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.12);
  display: flex;
  flex-direction: column;
  transition: transform 300ms cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}

.slider-panel.slider-right {
  right: 0;
}

.slider-panel.slider-left {
  left: 0;
}

.slider-panel.slider-dragging {
  transition: none;
}

.slider-handle {
  position: absolute;
  top: 50%;
  left: -4px;
  transform: translateY(-50%);
  width: 8px;
  height: 48px;
  cursor: ew-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
}

.slider-left .slider-handle {
  left: auto;
  right: -4px;
}

.handle-bar {
  width: 3px;
  height: 32px;
  background: #cbd5e1;
  border-radius: 2px;
}

.slider-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
}

.slider-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
}

.collaboration-status-bar {
  display: flex;
  gap: 12px;
  padding: 12px 20px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.status-label {
  color: #64748b;
}

.slider-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  -webkit-overflow-scrolling: touch;
}

.placeholder-content {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #94a3b8;
  font-size: 14px;
}

.slider-footer {
  padding: 12px 20px;
  border-top: 1px solid #e2e8f0;
  flex-shrink: 0;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
