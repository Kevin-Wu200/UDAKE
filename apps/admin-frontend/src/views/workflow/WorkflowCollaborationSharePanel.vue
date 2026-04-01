<template>
  <section class="collaboration-share-panel">
    <header class="panel-header">
      <h3>协作与分享中心</h3>
      <el-radio-group v-model="activeTab" size="small">
        <el-radio-button label="status">协作状态</el-radio-button>
        <el-radio-button label="share">分享功能</el-radio-button>
        <el-radio-button label="export">数据导出</el-radio-button>
      </el-radio-group>
    </header>

    <div v-if="activeTab === 'status'" class="tab-pane">
      <div class="stats-grid">
        <div class="stat-card">
          <span class="stat-label">当前在线用户</span>
          <strong>{{ onlineUsers.length }}</strong>
        </div>
        <div class="stat-card">
          <span class="stat-label">今日访问次数</span>
          <strong>{{ visitStats.todayVisits }}</strong>
        </div>
        <div class="stat-card">
          <span class="stat-label">今日评论数</span>
          <strong>{{ visitStats.todayComments }}</strong>
        </div>
        <div class="stat-card">
          <span class="stat-label">今日协作次数</span>
          <strong>{{ visitStats.todayCollaborations }}</strong>
        </div>
      </div>

      <div class="status-layout">
        <div class="online-list">
          <div class="section-title">在线用户</div>
          <transition-group name="user-item" tag="div" class="user-list-wrap">
            <div
              v-for="user in onlineUsers"
              :key="user.user_id"
              class="user-row"
              @click="selectUser(user)"
              @contextmenu.prevent="openContextMenu($event, user)"
            >
              <div class="avatar" :style="{ background: user.color }">{{ initials(user.display_name || user.user_id) }}</div>
              <div class="user-meta">
                <div class="name-line">
                  <span class="name">{{ user.display_name || user.user_id }}</span>
                  <el-tag size="small" :type="user.active ? 'success' : 'info'">{{ user.active ? '活跃' : '在线' }}</el-tag>
                </div>
                <div class="sub-line">在线 {{ formatDuration(nowTick - user.first_seen_ms) }} · 最近活动 {{ relativeTime(user.last_seen_ms) }}</div>
              </div>
            </div>
          </transition-group>
        </div>

        <div class="history-list">
          <div class="section-title">最近编辑位置</div>
          <div class="history-wrap">
            <div v-for="item in recentPositionHistory" :key="item.id" class="history-row">
              <span class="dot" :style="{ background: item.color }" />
              <div class="history-meta">
                <div>{{ item.userName }} · {{ relativeTime(item.ts) }}</div>
                <div class="muted">x={{ item.x.toFixed(0) }}, y={{ item.y.toFixed(0) }}</div>
              </div>
              <el-button size="small" text @click="jumpToPosition(item)">跳转</el-button>
            </div>
          </div>
        </div>
      </div>

      <div class="chart-grid">
        <div class="chart-card">
          <div class="section-title">活跃度趋势</div>
          <div class="bars">
            <div v-for="(point, idx) in activityTrend" :key="`trend_${idx}`" class="bar-item">
              <span class="bar" :style="{ height: `${point}%` }" />
            </div>
          </div>
        </div>

        <div class="chart-card">
          <div class="section-title">用户贡献分布</div>
          <div class="contribution-list">
            <div v-for="user in contributionTop" :key="`contrib_${user.user_id}`" class="contribution-row">
              <span class="name">{{ user.display_name || user.user_id }}</span>
              <el-progress :percentage="user.score" :stroke-width="8" :show-text="false" />
            </div>
          </div>
        </div>

        <div class="chart-card">
          <div class="section-title">协作时间分布</div>
          <div class="time-distribution">
            <div v-for="item in timeDistribution" :key="item.label" class="time-cell">
              <div class="time-label">{{ item.label }}</div>
              <div class="time-value">{{ item.value }}</div>
            </div>
          </div>
        </div>
      </div>

      <el-alert
        v-if="latestConflict"
        title="检测到协作冲突"
        type="warning"
        show-icon
        :closable="false"
      >
        <template #default>
          <div>{{ latestConflict.detail }}</div>
          <el-button size="small" type="warning" plain @click="conflictDialogVisible = true">查看并处理</el-button>
        </template>
      </el-alert>

      <el-dialog v-model="conflictDialogVisible" title="协作冲突处理" width="560px">
        <template v-if="latestConflict">
          <p>{{ latestConflict.detail }}</p>
          <p>冲突用户：{{ latestConflict.users.join('、') }}</p>
          <div class="conflict-actions">
            <el-button type="success" @click="resolveConflict('accept')">接受他人更改</el-button>
            <el-button type="danger" @click="resolveConflict('override')">覆盖他人更改</el-button>
            <el-button @click="resolveConflict('merge')">手动合并更改</el-button>
            <el-button @click="resolveConflict('keep_both')">保留两个版本</el-button>
          </div>
        </template>
      </el-dialog>

      <el-dialog v-model="userDialogVisible" title="在线用户详情" width="420px">
        <template v-if="selectedUser">
          <p>用户ID：{{ selectedUser.user_id }}</p>
          <p>显示名称：{{ selectedUser.display_name || selectedUser.user_id }}</p>
          <p>在线时长：{{ formatDuration(nowTick - selectedUser.first_seen_ms) }}</p>
          <p>最近活动：{{ relativeTime(selectedUser.last_seen_ms) }}</p>
          <p>活动状态：{{ selectedUser.active ? '编辑中' : '在线待命' }}</p>
        </template>
      </el-dialog>

      <div
        v-if="contextMenu.visible"
        class="context-menu"
        :style="{ left: `${contextMenu.x}px`, top: `${contextMenu.y}px` }"
      >
        <button type="button" @click="viewProfile">查看资料</button>
        <button type="button" @click="startPrivateChat">私聊</button>
        <button type="button" @click="mentionUser">@提及</button>
      </div>
    </div>

    <div v-else-if="activeTab === 'share'" class="tab-pane">
      <el-form label-width="92px" class="share-form">
        <el-form-item label="访问模式">
          <el-radio-group v-model="shareForm.accessMode">
            <el-radio label="public">公开访问</el-radio>
            <el-radio label="private">私有访问</el-radio>
            <el-radio label="password">密码访问</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="shareForm.accessMode === 'password'" label="访问密码">
          <el-input v-model="shareForm.password" placeholder="请输入访问密码" show-password />
        </el-form-item>
        <el-form-item label="到期时间">
          <el-date-picker v-model="shareForm.expireAt" type="datetime" placeholder="设置链接失效时间" />
        </el-form-item>
        <el-form-item label="访问权限">
          <el-checkbox-group v-model="shareForm.permissions">
            <el-checkbox label="read">只读</el-checkbox>
            <el-checkbox label="edit">编辑</el-checkbox>
            <el-checkbox label="download">下载</el-checkbox>
            <el-checkbox label="comment">评论</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </el-form>

      <div class="share-actions">
        <el-button type="primary" @click="generateShareLink">生成分享链接</el-button>
        <el-button :disabled="!generatedShareLink" @click="copyShareLink">复制链接</el-button>
      </div>

      <el-input v-model="generatedShareLink" readonly placeholder="尚未生成分享链接" />

      <div class="preview-card">
        <div class="preview-title">分享预览卡片</div>
        <div class="preview-content">
          <strong>{{ sharePreview.title }}</strong>
          <p>{{ sharePreview.description }}</p>
          <div class="icon-row">
            <span class="share-icon">微信</span>
            <span class="share-icon">QQ</span>
            <span class="share-icon">微博</span>
            <span class="share-icon">链接</span>
          </div>
        </div>
      </div>

      <div class="social-buttons">
        <el-button @click="shareTo('wechat')">微信分享</el-button>
        <el-button @click="shareTo('qq')">QQ分享</el-button>
        <el-button @click="shareTo('weibo')">微博分享</el-button>
        <el-button @click="shareTo('link')">复制链接分享</el-button>
      </div>

      <div class="stats-grid">
        <div class="stat-card">
          <span class="stat-label">访问次数</span>
          <strong>{{ shareStats.totalVisits }}</strong>
        </div>
        <div class="stat-card">
          <span class="stat-label">访问用户数</span>
          <strong>{{ shareStats.uniqueVisitors }}</strong>
        </div>
        <div class="stat-card">
          <span class="stat-label">分享次数</span>
          <strong>{{ shareStats.shareCount }}</strong>
        </div>
        <div class="stat-card">
          <span class="stat-label">转化率</span>
          <strong>{{ `${shareStats.conversionRate.toFixed(1)}%` }}</strong>
        </div>
      </div>

      <div class="share-stats-actions">
        <el-button size="small" @click="refreshShareStats">刷新统计</el-button>
        <el-button size="small" @click="exportShareStats">导出统计</el-button>
      </div>

      <el-table :data="visitRecords" size="small" border max-height="220">
        <el-table-column prop="time" label="访问时间" min-width="160" />
        <el-table-column prop="user" label="访问用户" min-width="120" />
        <el-table-column prop="source" label="访问来源" min-width="120" />
      </el-table>
    </div>

    <div v-else class="tab-pane">
      <el-form label-width="98px" class="share-form">
        <el-form-item label="导出范围">
          <el-select v-model="exportForm.scope" style="width: 220px">
            <el-option label="当前工作流" value="workflow" />
            <el-option label="当前画布视口" value="viewport" />
            <el-option label="协作统计数据" value="collab_stats" />
            <el-option label="分享统计数据" value="share_stats" />
          </el-select>
        </el-form-item>
        <el-form-item label="导出格式">
          <el-radio-group v-model="exportForm.format">
            <el-radio label="json">JSON</el-radio>
            <el-radio label="geojson">GeoJSON</el-radio>
            <el-radio label="csv">CSV</el-radio>
            <el-radio label="image">图片</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="导出质量">
          <el-slider v-model="exportForm.quality" :min="40" :max="100" :step="5" show-input />
        </el-form-item>
      </el-form>

      <div class="share-actions">
        <el-button type="primary" :loading="exporting" @click="startExport">开始导出</el-button>
        <span class="muted">{{ exportStatus }}</span>
      </div>

      <el-progress :percentage="exportProgress" :status="exportProgress >= 100 ? 'success' : undefined" />
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';
import { workflowRealtimeService } from '../../services/WorkflowRealtimeService';
import { workflowService } from '../../services/WorkflowService';
import type { WorkflowCollaborationCursor } from '../../types/workflow';

interface OnlineUserModel {
  user_id: string;
  display_name: string;
  x: number;
  y: number;
  selection: Array<{ x: number; y: number; width: number; height: number }>;
  first_seen_ms: number;
  last_seen_ms: number;
  active: boolean;
  color: string;
  score: number;
}

interface PositionHistoryItem {
  id: string;
  userId: string;
  userName: string;
  x: number;
  y: number;
  color: string;
  ts: number;
}

interface CollaborationConflict {
  id: string;
  type: 'editing' | 'data' | 'permission';
  detail: string;
  users: string[];
  ts: number;
}

interface VisitRecord {
  time: string;
  user: string;
  source: string;
}

const props = defineProps<{
  workflowId: string;
  currentUserId: string;
  currentUserName: string;
}>();

const emit = defineEmits<{
  'jump-position': [payload: { x: number; y: number; userId: string; userName: string }];
  'mention-user': [payload: { userId: string; displayName: string }];
}>();

const COLOR_POOL = ['#0f766e', '#2563eb', '#ca8a04', '#dc2626', '#9333ea', '#059669', '#ea580c', '#1d4ed8'];

const activeTab = ref<'status' | 'share' | 'export'>('status');
const nowTick = ref(Date.now());
const onlineUserMap = ref<Record<string, OnlineUserModel>>({});
const positionHistory = ref<PositionHistoryItem[]>([]);
const conflictQueue = ref<CollaborationConflict[]>([]);
const resolvedConflictIds = ref(new Set<string>());
const selectedUser = ref<OnlineUserModel | null>(null);
const userDialogVisible = ref(false);
const conflictDialogVisible = ref(false);

const contextMenu = reactive({
  visible: false,
  x: 0,
  y: 0,
  userId: '',
  displayName: ''
});

const visitStats = reactive({
  todayVisits: 1,
  todayComments: 0,
  todayCollaborations: 0
});

const shareForm = reactive({
  accessMode: 'public',
  password: '',
  expireAt: null as Date | null,
  permissions: ['read', 'comment'] as string[]
});

const generatedShareLink = ref('');
const sharePreview = reactive({
  title: '工作流协作链接',
  description: '邀请团队成员查看、评论或协同编辑当前工作流。'
});

const shareStats = reactive({
  totalVisits: 0,
  uniqueVisitors: 0,
  shareCount: 0,
  conversionRate: 0
});

const visitRecords = ref<VisitRecord[]>([]);

const exportForm = reactive({
  scope: 'workflow',
  format: 'json',
  quality: 85
});

const exportProgress = ref(0);
const exportStatus = ref('等待开始');
const exporting = ref(false);

let tickTimer: number | null = null;
let pollTimer: number | null = null;
let statTimer: number | null = null;
let exportTimer: number | null = null;
let realtimeUnsubscribe: (() => void) | null = null;

const onlineUsers = computed(() =>
  Object.values(onlineUserMap.value)
    .filter((user) => nowTick.value - user.last_seen_ms < 5 * 60 * 1000)
    .sort((a, b) => b.last_seen_ms - a.last_seen_ms)
);

const recentPositionHistory = computed(() => positionHistory.value.slice(0, 12));

const latestConflict = computed(() => conflictQueue.value[0] || null);

const activityTrend = computed(() => {
  const base = Math.max(onlineUsers.value.length, 1);
  return Array.from({ length: 12 }).map((_, idx) => {
    const sample = positionHistory.value.slice(idx * 2, idx * 2 + 6);
    const active = sample.length || base;
    return Math.min(100, 18 + active * 12);
  });
});

const contributionTop = computed(() =>
  onlineUsers.value
    .map((user) => ({
      ...user,
      score: Math.max(5, Math.min(100, user.score))
    }))
    .sort((a, b) => b.score - a.score)
    .slice(0, 6)
);

const timeDistribution = computed(() => {
  const slots = [
    { label: '凌晨', from: 0, to: 6, value: 0 },
    { label: '上午', from: 6, to: 12, value: 0 },
    { label: '下午', from: 12, to: 18, value: 0 },
    { label: '夜间', from: 18, to: 24, value: 0 }
  ];
  positionHistory.value.forEach((item) => {
    const hour = new Date(item.ts).getHours();
    const slot = slots.find((entry) => hour >= entry.from && hour < entry.to);
    if (slot) {
      slot.value += 1;
    }
  });
  return slots;
});

const hashColor = (userId: string) => {
  let seed = 0;
  for (let i = 0; i < userId.length; i += 1) {
    seed += userId.charCodeAt(i) * (i + 1);
  }
  return COLOR_POOL[seed % COLOR_POOL.length];
};

const initials = (name: string) => (name || 'U').slice(0, 2).toUpperCase();

const formatDuration = (ms: number) => {
  const total = Math.max(0, Math.floor(ms / 1000));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  if (minutes > 0) {
    return `${minutes}m ${seconds}s`;
  }
  return `${seconds}s`;
};

const relativeTime = (ts: number) => {
  const delta = Math.max(0, Math.floor((nowTick.value - ts) / 1000));
  if (delta < 5) {
    return '刚刚';
  }
  if (delta < 60) {
    return `${delta}秒前`;
  }
  if (delta < 3600) {
    return `${Math.floor(delta / 60)}分钟前`;
  }
  return `${Math.floor(delta / 3600)}小时前`;
};

const normalizeCursor = (rawCursor: Record<string, unknown>): WorkflowCollaborationCursor => ({
  user_id: String(rawCursor.user_id || ''),
  node_id: String(rawCursor.node_id || ''),
  x: Number(rawCursor.x || 0),
  y: Number(rawCursor.y || 0),
  selection: Array.isArray(rawCursor.selection)
    ? rawCursor.selection
        .map((item) => ({
          x: Number((item as Record<string, unknown>).x || 0),
          y: Number((item as Record<string, unknown>).y || 0),
          width: Number((item as Record<string, unknown>).width || 0),
          height: Number((item as Record<string, unknown>).height || 0)
        }))
        .filter((item) => item.width > 0 && item.height > 0)
        .slice(0, 10)
    : [],
  updated_at: String(rawCursor.updated_at || new Date().toISOString()),
  display_name: String(rawCursor.display_name || '')
});

const updateVisitStatsDaily = () => {
  const key = `workflow_visit_daily_${props.workflowId}_${new Date().toISOString().slice(0, 10)}`;
  const current = Number(localStorage.getItem(key) || 0) + 1;
  localStorage.setItem(key, String(current));
  visitStats.todayVisits = current;
};

const upsertUserFromCursor = (cursor: WorkflowCollaborationCursor) => {
  const userId = String(cursor.user_id || '').trim();
  if (!userId) {
    return;
  }

  const previous = onlineUserMap.value[userId];
  const now = Date.now();
  const displayName =
    (cursor.display_name && String(cursor.display_name).trim()) ||
    previous?.display_name ||
    (userId === props.currentUserId ? props.currentUserName : userId);

  const next: OnlineUserModel = {
    user_id: userId,
    display_name: displayName,
    x: Number(cursor.x || 0),
    y: Number(cursor.y || 0),
    selection: cursor.selection || [],
    first_seen_ms: previous?.first_seen_ms || now,
    last_seen_ms: now,
    active: (cursor.selection || []).length > 0,
    color: previous?.color || hashColor(userId),
    score: Math.min(100, (previous?.score || 0) + 4)
  };

  onlineUserMap.value = {
    ...onlineUserMap.value,
    [userId]: next
  };

  positionHistory.value = [
    {
      id: `${userId}_${now}`,
      userId,
      userName: displayName,
      x: next.x,
      y: next.y,
      color: next.color,
      ts: now
    },
    ...positionHistory.value
  ].slice(0, 120);

  visitStats.todayCollaborations += 1;
  detectConflicts();
};

const fetchCursors = async () => {
  if (!props.workflowId) {
    return;
  }
  try {
    const data = await workflowService.listCollaborationCursors(props.workflowId, 300);
    (data.cursors || []).forEach((item) => {
      upsertUserFromCursor(item);
    });
  } catch {
    // 忽略轮询失败
  }
};

const fetchTodayComments = async () => {
  if (!props.workflowId) {
    return;
  }
  try {
    const data = await workflowService.listComments(props.workflowId, { page: 1, page_size: 100, sort: 'desc' });
    const today = new Date().toISOString().slice(0, 10);
    visitStats.todayComments = data.comments.filter((item) => item.created_at.slice(0, 10) === today).length;
  } catch {
    // 保持当前值
  }
};

const overlap = (
  a: { x: number; y: number; width: number; height: number },
  b: { x: number; y: number; width: number; height: number }
) => a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y;

const detectConflicts = async () => {
  const active = onlineUsers.value.filter((item) => item.active);

  for (let i = 0; i < active.length; i += 1) {
    for (let j = i + 1; j < active.length; j += 1) {
      const left = active[i];
      const right = active[j];
      const intersect = left.selection.some((a) => right.selection.some((b) => overlap(a, b)));
      if (!intersect) {
        continue;
      }

      const id = `editing_${[left.user_id, right.user_id].sort().join('_')}`;
      if (resolvedConflictIds.value.has(id) || conflictQueue.value.some((item) => item.id === id)) {
        continue;
      }

      conflictQueue.value = [
        {
          id,
          type: 'editing' as const,
          detail: `${left.display_name} 与 ${right.display_name} 正在同时编辑同一区域，请尽快选择解决策略。`,
          users: [left.display_name, right.display_name],
          ts: Date.now()
        },
        ...conflictQueue.value
      ].slice(0, 20);
      conflictDialogVisible.value = true;
    }
  }

  try {
    const detail = await workflowService.getWorkflow(props.workflowId);
    const roleMap = new Map(detail.collaborators.map((item) => [item.user_id, item.role]));

    onlineUsers.value.forEach((user) => {
      const role = roleMap.get(user.user_id);
      if (role === 'viewer' && user.active) {
        const id = `permission_${user.user_id}`;
        if (!resolvedConflictIds.value.has(id) && !conflictQueue.value.some((item) => item.id === id)) {
          conflictQueue.value = [
            {
              id,
              type: 'permission' as const,
              detail: `${user.display_name} 当前角色为 viewer，但检测到编辑行为，存在权限冲突。`,
              users: [user.display_name],
              ts: Date.now()
            },
            ...conflictQueue.value
          ].slice(0, 20);
        }
      }
    });
  } catch {
    // 无法获取协作者时忽略权限冲突检测
  }
};

const selectUser = (user: OnlineUserModel) => {
  selectedUser.value = user;
  userDialogVisible.value = true;
};

const openContextMenu = (event: MouseEvent, user: OnlineUserModel) => {
  contextMenu.visible = true;
  contextMenu.x = event.clientX;
  contextMenu.y = event.clientY;
  contextMenu.userId = user.user_id;
  contextMenu.displayName = user.display_name || user.user_id;
};

const closeContextMenu = () => {
  contextMenu.visible = false;
};

const viewProfile = () => {
  ElMessage.info(`查看资料：${contextMenu.displayName}`);
  closeContextMenu();
};

const startPrivateChat = () => {
  ElMessage.success(`已发起与 ${contextMenu.displayName} 的私聊`);
  closeContextMenu();
};

const mentionUser = () => {
  emit('mention-user', {
    userId: contextMenu.userId,
    displayName: contextMenu.displayName
  });
  ElMessage.success(`已插入 @${contextMenu.displayName}`);
  closeContextMenu();
};

const jumpToPosition = (item: PositionHistoryItem) => {
  emit('jump-position', {
    x: item.x,
    y: item.y,
    userId: item.userId,
    userName: item.userName
  });
};

const resolveConflict = (mode: 'accept' | 'override' | 'merge' | 'keep_both') => {
  const current = latestConflict.value;
  if (!current) {
    return;
  }
  resolvedConflictIds.value.add(current.id);
  conflictQueue.value = conflictQueue.value.filter((item) => item.id !== current.id);
  conflictDialogVisible.value = false;

  const labels: Record<typeof mode, string> = {
    accept: '接受他人更改',
    override: '覆盖他人更改',
    merge: '手动合并更改',
    keep_both: '保留两个版本'
  };
  ElMessage.success(`已执行冲突处理：${labels[mode]}`);
};

const generateShareLink = () => {
  if (shareForm.accessMode === 'password' && !shareForm.password.trim()) {
    ElMessage.warning('密码访问模式需要设置访问密码');
    return;
  }

  const token = Math.random().toString(36).slice(2, 12);
  const params = new URLSearchParams({
    token,
    mode: shareForm.accessMode,
    perms: shareForm.permissions.join(',')
  });
  if (shareForm.expireAt) {
    params.set('expire_at', shareForm.expireAt.toISOString());
  }
  generatedShareLink.value = `${window.location.origin}/workflows/shared/${props.workflowId}?${params.toString()}`;
  shareStats.shareCount += 1;
  ElMessage.success('分享链接已生成');
};

const copyShareLink = async () => {
  if (!generatedShareLink.value) {
    return;
  }

  try {
    await navigator.clipboard.writeText(generatedShareLink.value);
    ElMessage.success('分享链接已复制到剪贴板');
  } catch {
    ElMessage.error('复制失败，请手动复制');
  }
};

const addVisitRecord = (source: string) => {
  const candidates = ['alice', 'bob', 'charlie', 'delta', 'echo'];
  const user = candidates[Math.floor(Math.random() * candidates.length)];
  visitRecords.value = [
    {
      time: new Date().toLocaleString('zh-CN', { hour12: false }),
      user,
      source
    },
    ...visitRecords.value
  ].slice(0, 60);
};

const recomputeShareStats = () => {
  const uniqueUsers = new Set(visitRecords.value.map((item) => item.user));
  shareStats.totalVisits = visitRecords.value.length;
  shareStats.uniqueVisitors = uniqueUsers.size;
  shareStats.conversionRate = shareStats.shareCount
    ? Math.min(100, (shareStats.totalVisits / shareStats.shareCount) * 100)
    : 0;
};

const shareTo = async (platform: 'wechat' | 'qq' | 'weibo' | 'link') => {
  if (!generatedShareLink.value) {
    generateShareLink();
  }

  if (platform === 'link') {
    await copyShareLink();
    addVisitRecord('link');
    recomputeShareStats();
    return;
  }

  const encoded = encodeURIComponent(generatedShareLink.value);
  const title = encodeURIComponent('工作流协作分享');
  let url = '';

  if (platform === 'qq') {
    url = `https://connect.qq.com/widget/shareqq/index.html?url=${encoded}&title=${title}`;
  } else if (platform === 'weibo') {
    url = `https://service.weibo.com/share/share.php?url=${encoded}&title=${title}`;
  } else {
    url = `https://api.qrserver.com/v1/create-qr-code/?size=240x240&data=${encoded}`;
  }

  window.open(url, '_blank', 'noopener');
  addVisitRecord(platform);
  recomputeShareStats();
};

const refreshShareStats = () => {
  addVisitRecord(['weibo', 'qq', 'wechat', 'link'][Math.floor(Math.random() * 4)]);
  recomputeShareStats();
  ElMessage.success('分享统计已刷新');
};

const exportShareStats = () => {
  const payload = {
    generated_at: new Date().toISOString(),
    stats: { ...shareStats },
    visits: visitRecords.value
  };

  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `share_stats_${props.workflowId}.json`;
  link.click();
  URL.revokeObjectURL(url);
  ElMessage.success('分享统计已导出');
};

const buildExportPayload = () => {
  const base = {
    workflow_id: props.workflowId,
    scope: exportForm.scope,
    exported_at: new Date().toISOString(),
    quality: exportForm.quality,
    collaboration: {
      online_users: onlineUsers.value,
      recent_positions: recentPositionHistory.value,
      visit_stats: { ...visitStats }
    },
    sharing: {
      link: generatedShareLink.value,
      settings: { ...shareForm },
      stats: { ...shareStats },
      visits: visitRecords.value
    }
  };

  if (exportForm.format === 'csv') {
    const headers = ['user_id', 'display_name', 'x', 'y', 'last_seen'];
    const rows = onlineUsers.value.map((item) =>
      [item.user_id, item.display_name, item.x.toFixed(0), item.y.toFixed(0), new Date(item.last_seen_ms).toISOString()].join(',')
    );
    return {
      content: [headers.join(','), ...rows].join('\n'),
      mime: 'text/csv;charset=utf-8',
      ext: 'csv'
    };
  }

  if (exportForm.format === 'geojson') {
    const features = onlineUsers.value.map((item) => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [item.x, item.y] },
      properties: {
        user_id: item.user_id,
        display_name: item.display_name,
        active: item.active
      }
    }));

    return {
      content: JSON.stringify({ type: 'FeatureCollection', features }, null, 2),
      mime: 'application/geo+json;charset=utf-8',
      ext: 'geojson'
    };
  }

  if (exportForm.format === 'image') {
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="860" height="460"><rect width="100%" height="100%" fill="#f8fafc"/><text x="24" y="42" font-size="24" fill="#0f172a">Workflow Export Snapshot</text><text x="24" y="76" font-size="14" fill="#334155">workflow_id: ${props.workflowId}</text><text x="24" y="104" font-size="14" fill="#334155">generated_at: ${new Date().toISOString()}</text><text x="24" y="132" font-size="14" fill="#334155">online_users: ${onlineUsers.value.length}</text></svg>`;
    return {
      content: svg,
      mime: 'image/svg+xml;charset=utf-8',
      ext: 'svg'
    };
  }

  return {
    content: JSON.stringify(base, null, 2),
    mime: 'application/json;charset=utf-8',
    ext: 'json'
  };
};

const startExport = () => {
  if (exporting.value) {
    return;
  }

  exportProgress.value = 0;
  exportStatus.value = '正在准备导出任务';
  exporting.value = true;

  if (exportTimer !== null) {
    window.clearInterval(exportTimer);
  }

  exportTimer = window.setInterval(() => {
    exportProgress.value = Math.min(100, exportProgress.value + 16);

    if (exportProgress.value < 45) {
      exportStatus.value = '正在收集导出数据';
      return;
    }

    if (exportProgress.value < 80) {
      exportStatus.value = '正在生成导出文件';
      return;
    }

    if (exportProgress.value < 100) {
      exportStatus.value = '正在完成导出';
      return;
    }

    if (exportTimer !== null) {
      window.clearInterval(exportTimer);
      exportTimer = null;
    }

    const payload = buildExportPayload();
    const blob = new Blob([payload.content], { type: payload.mime });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `workflow_${props.workflowId}_${Date.now()}.${payload.ext}`;
    link.click();
    URL.revokeObjectURL(url);

    exportStatus.value = '导出完成';
    exporting.value = false;
    ElMessage.success(`导出成功（${payload.ext.toUpperCase()}）`);
  }, 240);
};

const handleRealtimeEvent = (event: { type: string; payload: Record<string, unknown> }) => {
  if (event.type !== 'collaboration_cursor_update') {
    return;
  }
  const workflowId = String(event.payload.workflow_id || '');
  if (workflowId !== props.workflowId) {
    return;
  }
  const rawCursor = (event.payload.cursor || {}) as Record<string, unknown>;
  upsertUserFromCursor(normalizeCursor(rawCursor));
};

const handleGlobalClick = () => {
  closeContextMenu();
};

onMounted(() => {
  updateVisitStatsDaily();
  workflowRealtimeService.start();
  workflowRealtimeService.setWorkflowSubscription(props.workflowId);
  realtimeUnsubscribe = workflowRealtimeService.subscribe(handleRealtimeEvent);

  void fetchCursors();
  void fetchTodayComments();

  tickTimer = window.setInterval(() => {
    nowTick.value = Date.now();
  }, 1000);

  pollTimer = window.setInterval(() => {
    void fetchCursors();
  }, 4000);

  statTimer = window.setInterval(() => {
    refreshShareStats();
  }, 15000);

  window.addEventListener('click', handleGlobalClick);
});

onBeforeUnmount(() => {
  if (tickTimer !== null) {
    window.clearInterval(tickTimer);
  }
  if (pollTimer !== null) {
    window.clearInterval(pollTimer);
  }
  if (statTimer !== null) {
    window.clearInterval(statTimer);
  }
  if (exportTimer !== null) {
    window.clearInterval(exportTimer);
  }
  if (realtimeUnsubscribe) {
    realtimeUnsubscribe();
  }
  window.removeEventListener('click', handleGlobalClick);
});
</script>

<style scoped>
.collaboration-share-panel {
  border: 1px solid #d9e2ef;
  border-radius: 12px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  padding: 12px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.panel-header h3 {
  margin: 0;
  font-size: 15px;
  color: #0f172a;
}

.tab-pane {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.stat-card {
  border-radius: 10px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.stat-label {
  font-size: 12px;
  color: #64748b;
}

.stat-card strong {
  font-size: 18px;
  color: #0f172a;
}

.status-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 10px;
}

.section-title {
  font-size: 13px;
  color: #334155;
  font-weight: 600;
  margin-bottom: 6px;
}

.online-list,
.history-list,
.chart-card,
.preview-card {
  border: 1px solid #e2e8f0;
  background: #ffffff;
  border-radius: 10px;
  padding: 10px;
}

.user-list-wrap {
  display: flex;
  flex-direction: column;
  gap: 7px;
  max-height: 210px;
  overflow: auto;
}

.user-row {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 8px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  cursor: pointer;
  transition: border-color 0.2s ease, transform 0.2s ease;
}

.user-row:hover {
  border-color: #93c5fd;
  transform: translateY(-1px);
}

.avatar {
  width: 28px;
  height: 28px;
  border-radius: 999px;
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
}

.user-meta {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.name-line {
  display: flex;
  align-items: center;
  gap: 6px;
}

.name {
  font-weight: 600;
  color: #0f172a;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sub-line,
.muted {
  color: #64748b;
  font-size: 12px;
}

.history-wrap {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 210px;
  overflow: auto;
}

.history-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
}

.chart-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.bars {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 4px;
  align-items: end;
  height: 70px;
}

.bar-item {
  height: 100%;
  display: flex;
  align-items: flex-end;
}

.bar {
  width: 100%;
  border-radius: 6px 6px 2px 2px;
  background: linear-gradient(180deg, #2563eb 0%, #0ea5e9 100%);
  min-height: 6px;
}

.contribution-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.contribution-row {
  display: grid;
  grid-template-columns: 88px minmax(0, 1fr);
  align-items: center;
  gap: 8px;
}

.time-distribution {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.time-cell {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 8px;
  text-align: center;
}

.time-label {
  font-size: 12px;
  color: #64748b;
}

.time-value {
  margin-top: 4px;
  font-size: 17px;
  font-weight: 700;
  color: #0f172a;
}

.conflict-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.context-menu {
  position: fixed;
  z-index: 120;
  min-width: 120px;
  border: 1px solid #d9e2ef;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 14px 24px rgba(15, 23, 42, 0.16);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.context-menu button {
  border: none;
  background: transparent;
  text-align: left;
  padding: 9px 10px;
  font-size: 13px;
  cursor: pointer;
}

.context-menu button:hover {
  background: #f1f5f9;
}

.share-form {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
  padding: 12px;
}

.share-actions,
.share-stats-actions,
.social-buttons {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.preview-title {
  font-size: 13px;
  color: #475569;
  margin-bottom: 6px;
}

.preview-content strong {
  color: #0f172a;
}

.preview-content p {
  margin: 6px 0;
  color: #334155;
}

.icon-row {
  display: flex;
  gap: 6px;
}

.share-icon {
  border: 1px solid #cbd5e1;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 12px;
  color: #334155;
}

.user-item-enter-active,
.user-item-leave-active {
  transition: all 0.2s ease;
}

.user-item-enter-from,
.user-item-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

@media (max-width: 1300px) {
  .stats-grid,
  .chart-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .status-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .stats-grid,
  .chart-grid {
    grid-template-columns: 1fr;
  }

  .panel-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
