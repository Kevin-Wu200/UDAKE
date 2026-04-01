<template>
  <div class="cursor-layer">
    <canvas ref="selectionCanvasRef" class="selection-canvas" />
    <div
      v-for="cursor in visibleCursors"
      :key="cursor.user_id"
      class="remote-cursor"
      :class="{ inactive: cursor.inactive }"
      :style="cursorStyle(cursor)"
    >
      <div class="cursor-pointer" :style="{ '--cursor-color': cursor.color }" />
      <div class="cursor-label" :style="{ '--cursor-color': cursor.color }">
        <span class="avatar">{{ initials(cursor.display_name || cursor.user_id) }}</span>
        <span class="name">{{ cursor.display_name || cursor.user_id }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { workflowRealtimeService } from '../../services/WorkflowRealtimeService';
import { workflowService } from '../../services/WorkflowService';
import type { WorkflowCollaborationCursor, WorkflowCursorSelectionRect } from '../../types/workflow';

interface CursorViewModel extends WorkflowCollaborationCursor {
  color: string;
  display_name?: string;
  inactive: boolean;
  last_seen_ms: number;
}

const props = defineProps<{
  workflowId: string;
  targetEl: HTMLElement | null;
  currentUserId: string;
  currentUserName?: string;
}>();

const selectionCanvasRef = ref<HTMLCanvasElement | null>(null);
const cursorMap = ref<Record<string, CursorViewModel>>({});
const lastLocalSelection = ref<WorkflowCursorSelectionRect[]>([]);
const syncBlocked = ref(false);
let pollTimer: number | null = null;
let refreshTimer: number | null = null;
let unsubscribeRealtime: (() => void) | null = null;
let lastPersistAt = 0;
let rafId: number | null = null;
let boundTargetEl: HTMLElement | null = null;

const COLOR_POOL = ['#0f766e', '#2563eb', '#ca8a04', '#dc2626', '#9333ea', '#059669', '#ea580c', '#1d4ed8'];
const UPDATE_THROTTLE_MS = 100;
const PERSIST_MIN_GAP_MS = 1200;
const HIDE_TIMEOUT_MS = 5 * 60 * 1000;
const USER_CACHE_KEY = 'udake_workflow_cursor_user_cache_v1';
const userNameCache = ref<Record<string, string>>({});

const visibleCursors = computed(() => {
  const now = Date.now();
  return Object.values(cursorMap.value)
    .filter((item) => item.user_id !== props.currentUserId)
    .filter((item) => now - item.last_seen_ms <= HIDE_TIMEOUT_MS)
    .map((item) => ({
      ...item,
      inactive: now - item.last_seen_ms > 15_000
    }));
});

const throttle = <T extends (...args: any[]) => void>(fn: T, wait: number) => {
  let last = 0;
  return (...args: Parameters<T>) => {
    const now = Date.now();
    if (now - last < wait) {
      return;
    }
    last = now;
    fn(...args);
  };
};

const normalizeSelection = (selection: unknown): WorkflowCursorSelectionRect[] => {
  if (!Array.isArray(selection)) {
    return [];
  }
  return selection
    .map((item) => ({
      x: Number((item as Record<string, unknown>).x ?? 0),
      y: Number((item as Record<string, unknown>).y ?? 0),
      width: Number((item as Record<string, unknown>).width ?? 0),
      height: Number((item as Record<string, unknown>).height ?? 0)
    }))
    .filter((item) => Number.isFinite(item.x) && Number.isFinite(item.y) && item.width > 0 && item.height > 0)
    .slice(0, 12);
};

const hashColor = (userId: string) => {
  let seed = 0;
  for (let i = 0; i < userId.length; i += 1) {
    seed += userId.charCodeAt(i) * (i + 1);
  }
  return COLOR_POOL[seed % COLOR_POOL.length];
};

const getTargetRect = () => props.targetEl?.getBoundingClientRect() ?? null;

const scheduleCanvasRender = () => {
  if (rafId !== null) {
    return;
  }
  rafId = requestAnimationFrame(() => {
    rafId = null;
    drawSelectionCanvas();
  });
};

const drawSelectionCanvas = () => {
  const canvas = selectionCanvasRef.value;
  const target = props.targetEl;
  if (!canvas || !target) {
    return;
  }

  const rect = target.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  const width = Math.max(1, Math.floor(rect.width));
  const height = Math.max(1, Math.floor(rect.height));
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    return;
  }
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, width, height);

  visibleCursors.value.forEach((cursor) => {
    const alpha = cursor.inactive ? 0.08 : 0.16;
    const borderAlpha = cursor.inactive ? 0.32 : 0.58;
    cursor.selection.forEach((area) => {
      ctx.fillStyle = hexToRgba(cursor.color, alpha);
      ctx.strokeStyle = hexToRgba(cursor.color, borderAlpha);
      ctx.lineWidth = 1.2;
      ctx.fillRect(area.x, area.y, area.width, area.height);
      ctx.strokeRect(area.x, area.y, area.width, area.height);
    });
  });
};

const hexToRgba = (hex: string, alpha: number) => {
  const clean = hex.replace('#', '');
  const value = clean.length === 3 ? clean.split('').map((c) => `${c}${c}`).join('') : clean;
  const num = Number.parseInt(value, 16);
  const r = (num >> 16) & 255;
  const g = (num >> 8) & 255;
  const b = num & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};

const cursorStyle = (cursor: CursorViewModel) => ({
  transform: `translate3d(${cursor.x}px, ${cursor.y}px, 0)`
});

const initials = (name: string) => (name || 'U').slice(0, 2).toUpperCase();

const loadUserCache = () => {
  try {
    const raw = localStorage.getItem(USER_CACHE_KEY);
    if (!raw) {
      userNameCache.value = {};
      return;
    }
    const parsed = JSON.parse(raw) as Record<string, string>;
    userNameCache.value = parsed || {};
  } catch {
    userNameCache.value = {};
  }
};

const saveUserCache = () => {
  try {
    localStorage.setItem(USER_CACHE_KEY, JSON.stringify(userNameCache.value));
  } catch {
    // 忽略存储异常
  }
};

const upsertCursor = (payload: WorkflowCollaborationCursor) => {
  const uid = String(payload.user_id || '').trim();
  if (!uid) {
    return;
  }

  const previous = cursorMap.value[uid];
  const incomingName = String(payload.display_name || '').trim();
  if (incomingName) {
    userNameCache.value = {
      ...userNameCache.value,
      [uid]: incomingName
    };
    saveUserCache();
  }
  const displayName =
    uid === props.currentUserId
      ? props.currentUserName || uid
      : incomingName || previous?.display_name || userNameCache.value[uid] || uid;
  cursorMap.value = {
    ...cursorMap.value,
    [uid]: {
      ...payload,
      selection: normalizeSelection(payload.selection),
      color: previous?.color || hashColor(uid),
      display_name: displayName,
      inactive: false,
      last_seen_ms: Date.now()
    }
  };
  scheduleCanvasRender();
};

const handleRealtimeEvent = (event: { type: string; payload: Record<string, unknown> }) => {
  if (event.type !== 'collaboration_cursor_update') {
    return;
  }
  const payloadWorkflowId = String(event.payload.workflow_id || '');
  if (!payloadWorkflowId || payloadWorkflowId !== props.workflowId) {
    return;
  }

  const rawCursor = (event.payload.cursor || {}) as Record<string, unknown>;
  upsertCursor({
    user_id: String(rawCursor.user_id || ''),
    node_id: String(rawCursor.node_id || ''),
    x: Number(rawCursor.x || 0),
    y: Number(rawCursor.y || 0),
    selection: normalizeSelection(rawCursor.selection),
    updated_at: String(rawCursor.updated_at || new Date().toISOString())
  });
};

const persistCursor = async (x: number, y: number, selection: WorkflowCursorSelectionRect[]) => {
  if (!props.workflowId || !props.currentUserId || syncBlocked.value) {
    return;
  }
  const now = Date.now();
  if (now - lastPersistAt < PERSIST_MIN_GAP_MS) {
    return;
  }
  lastPersistAt = now;

  try {
    await workflowService.updateCollaborationCursor(props.workflowId, props.currentUserId, {
      x,
      y,
      selection
    });
  } catch {
    syncBlocked.value = true;
    window.setTimeout(() => {
      syncBlocked.value = false;
    }, 10_000);
  }
};

const sendLocalCursor = async (x: number, y: number, selection: WorkflowCursorSelectionRect[]) => {
  if (!props.workflowId || !props.currentUserId) {
    return;
  }
  const cursor: WorkflowCollaborationCursor = {
    user_id: props.currentUserId,
    node_id: '',
    x,
    y,
    selection,
    updated_at: new Date().toISOString(),
    display_name: props.currentUserName || props.currentUserId
  };
  upsertCursor(cursor);
  workflowRealtimeService.publish('collaboration_cursor_update', {
    workflow_id: props.workflowId,
    cursor
  });
  await persistCursor(x, y, selection);
};

const collectSelectionRects = (): WorkflowCursorSelectionRect[] => {
  const rect = getTargetRect();
  if (!rect) {
    return [];
  }
  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0 || selection.isCollapsed) {
    return [];
  }
  const range = selection.getRangeAt(0);
  const list = Array.from(range.getClientRects())
    .map((item) => ({
      x: item.left - rect.left,
      y: item.top - rect.top,
      width: item.width,
      height: item.height
    }))
    .filter((item) => item.width > 2 && item.height > 2)
    .slice(0, 12);
  return list;
};

const onPointerMove = throttle((event: MouseEvent | TouchEvent) => {
  const rect = getTargetRect();
  if (!rect) {
    return;
  }

  const source = 'touches' in event ? event.touches[0] : event;
  if (!source) {
    return;
  }

  const x = source.clientX - rect.left;
  const y = source.clientY - rect.top;
  if (x < 0 || y < 0 || x > rect.width || y > rect.height) {
    return;
  }

  const selection = lastLocalSelection.value;
  void sendLocalCursor(x, y, selection);
}, UPDATE_THROTTLE_MS);

const onSelectionChange = throttle(() => {
  lastLocalSelection.value = collectSelectionRects();
  const me = cursorMap.value[props.currentUserId];
  if (me) {
    void sendLocalCursor(me.x, me.y, lastLocalSelection.value);
  }
}, 160);

const fetchRemoteCursors = async () => {
  if (!props.workflowId) {
    return;
  }
  try {
    const response = await workflowService.listCollaborationCursors(props.workflowId, 300);
    (response.cursors || []).forEach((item) => {
      upsertCursor(item);
    });
  } catch {
    // 轮询失败时保持现有渲染，不中断交互
  }
};

const bindEvents = () => {
  const target = props.targetEl;
  if (!target) {
    return;
  }
  boundTargetEl = target;
  target.addEventListener('mousemove', onPointerMove, { passive: true });
  target.addEventListener('touchmove', onPointerMove, { passive: true });
  document.addEventListener('selectionchange', onSelectionChange);
};

const unbindEvents = () => {
  if (boundTargetEl) {
    boundTargetEl.removeEventListener('mousemove', onPointerMove);
    boundTargetEl.removeEventListener('touchmove', onPointerMove);
    boundTargetEl = null;
  }
  document.removeEventListener('selectionchange', onSelectionChange);
};

onMounted(() => {
  loadUserCache();
  bindEvents();
  workflowRealtimeService.start();
  workflowRealtimeService.setWorkflowSubscription(props.workflowId);
  unsubscribeRealtime = workflowRealtimeService.subscribe(handleRealtimeEvent);
  void fetchRemoteCursors();
  pollTimer = window.setInterval(() => {
    void fetchRemoteCursors();
  }, 4_000);
  refreshTimer = window.setInterval(() => {
    scheduleCanvasRender();
  }, 5_000);
  scheduleCanvasRender();
});

watch(
  () => props.targetEl,
  () => {
    unbindEvents();
    bindEvents();
    scheduleCanvasRender();
  }
);

watch(
  () => props.workflowId,
  (workflowId) => {
    cursorMap.value = {};
    workflowRealtimeService.setWorkflowSubscription(workflowId);
    void fetchRemoteCursors();
  }
);

watch(
  visibleCursors,
  () => {
    scheduleCanvasRender();
  },
  { deep: true }
);

onBeforeUnmount(() => {
  unbindEvents();
  if (pollTimer !== null) {
    window.clearInterval(pollTimer);
  }
  if (refreshTimer !== null) {
    window.clearInterval(refreshTimer);
  }
  if (rafId !== null) {
    cancelAnimationFrame(rafId);
  }
  if (unsubscribeRealtime) {
    unsubscribeRealtime();
  }
});
</script>

<style scoped>
.cursor-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
  z-index: 20;
}

.selection-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.remote-cursor {
  position: absolute;
  left: 0;
  top: 0;
  will-change: transform, opacity;
  transition: transform 120ms linear, opacity 260ms ease;
  animation: cursor-fade-in 180ms ease-out;
}

.remote-cursor.inactive {
  opacity: 0.45;
}

.cursor-pointer {
  width: 14px;
  height: 14px;
  border-left: 2px solid var(--cursor-color);
  border-top: 2px solid var(--cursor-color);
  border-radius: 2px;
  transform: rotate(-45deg);
  box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.05), 0 8px 18px rgba(15, 23, 42, 0.24);
  animation: pointer-blink 1.1s ease-in-out infinite;
}

.cursor-label {
  margin-top: 6px;
  margin-left: 8px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: color-mix(in srgb, var(--cursor-color) 20%, #ffffff);
  border: 1px solid color-mix(in srgb, var(--cursor-color) 72%, #94a3b8);
  border-radius: 999px;
  box-shadow: 0 6px 20px rgba(15, 23, 42, 0.15);
  padding: 2px 8px 2px 2px;
  color: #0f172a;
  font-size: 12px;
  max-width: 220px;
}

.avatar {
  display: inline-flex;
  width: 20px;
  height: 20px;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: var(--cursor-color);
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  line-height: 1;
}

.name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@keyframes pointer-blink {
  0%,
  100% {
    opacity: 0.96;
  }
  50% {
    opacity: 0.6;
  }
}

@keyframes cursor-fade-in {
  from {
    opacity: 0;
    transform: translate3d(0, 0, 0) scale(0.92);
  }
  to {
    opacity: 1;
    transform: translate3d(0, 0, 0) scale(1);
  }
}
</style>
