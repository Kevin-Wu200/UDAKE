<template>
  <section class="notification-center">
    <header class="notification-header">
      <div class="title-wrap">
        <h3>{{ t('noticecenter') }}</h3>
        <el-tag size="small" effect="plain">{{ t('unread') }} {{ unreadCount }}</el-tag>
        <el-tag size="small" effect="plain">{{ t('filterresult') }} {{ filteredNotifications.length }}</el-tag>
      </div>
      <div class="header-actions">
        <el-button text size="small" @click="showSettings = !showSettings">{{ t('noticesettings') }}</el-button>
        <el-button text size="small" @click="markAllAsRead" :disabled="unreadCount === 0">{{ t('readall') }}</el-button>
        <el-button text size="small" :loading="loading" @click="refreshNotifications">{{ t('refresh') }}</el-button>
      </div>
    </header>

    <div class="quick-filter-row">
      <el-radio-group v-model="filters.singleType" size="small">
        <el-radio-button label="all">{{ t('all') }}</el-radio-button>
        <el-radio-button label="mention">{{ t('mention') }}</el-radio-button>
        <el-radio-button label="comment">{{ t('comment') }}</el-radio-button>
        <el-radio-button label="share">{{ t('share') }}</el-radio-button>
        <el-radio-button label="system">{{ t('system') }}</el-radio-button>
      </el-radio-group>
    </div>

    <div class="advanced-filter-row">
      <el-checkbox-group v-model="filters.multiTypes" size="small">
        <el-checkbox label="mention">{{ t('mention') }}</el-checkbox>
        <el-checkbox label="comment">{{ t('comment') }}</el-checkbox>
        <el-checkbox label="share">{{ t('share') }}</el-checkbox>
        <el-checkbox label="system">{{ t('system') }}</el-checkbox>
      </el-checkbox-group>
      <el-input v-model="filters.sourceKeyword" :placeholder="t('filtersource')" clearable size="small" style="width: 120px" />
      <el-input v-model="filters.textKeyword" :placeholder="t('keyword')" clearable size="small" style="width: 140px" />
      <el-switch v-model="filters.unreadOnly" inline-prompt :active-text="t('onlyunread')" :inactive-text="t('all')" />
      <el-button size="small" @click="resetFilters">{{ t('resetfilter') }}</el-button>
    </div>

    <div class="sort-row">
      <el-select v-model="sortBy" size="small" style="width: 130px">
        <el-option :label="t('bytime')" value="time" />
        <el-option :label="t('bytype')" value="type" />
        <el-option :label="t('bypriority')" value="priority" />
      </el-select>
      <el-switch v-model="groupByType" inline-prompt :active-text="t('typegrouping')" :inactive-text="t('ordinary')" />
      <el-switch v-model="unreadFirst" inline-prompt :active-text="t('unreadpine')" :inactive-text="t('naturalsorting')" />
      <el-button size="small" :disabled="selectedIds.length === 0" @click="markSelectedAsRead">
        {{ t('batchread') }} ({{ selectedIds.length }})
      </el-button>
    </div>

    <div v-if="showSettings" class="settings-panel">
      <h4>{{ t('notificationsettings') }}</h4>
      <div class="settings-grid">
        <el-switch v-model="preferences.types.mention" :active-text="t('mention')" />
        <el-switch v-model="preferences.types.comment" :active-text="t('comment')" />
        <el-switch v-model="preferences.types.share" :active-text="t('share')" />
        <el-switch v-model="preferences.types.system" :active-text="t('system')" />
      </div>
      <div class="settings-row">
        <span class="label">{{ t('notificationfrequency') }}</span>
        <el-select v-model="preferences.frequency" size="small" style="width: 150px">
          <el-option :label="t('intime')" value="realtime" />
          <el-option :label="'5' + t('minusummary')" value="5m" />
          <el-option :label="'15' + t('minusummary')" value="15m" />
          <el-option :label="t('daysummary')" value="daily" />
        </el-select>
      </div>
      <div class="settings-row">
        <span class="label">{{ t('notificationmethod') }}</span>
        <el-checkbox-group v-model="preferences.channels" size="small">
          <el-checkbox label="popup">{{ t('popupwindow') }}</el-checkbox>
          <el-checkbox label="list">{{ t('list') }}</el-checkbox>
          <el-checkbox label="email">{{ t('post') }}</el-checkbox>
        </el-checkbox-group>
      </div>
      <div class="settings-row">
        <span class="save-tip">{{ saveTip }}</span>
      </div>
      <div class="history-list" v-if="preferenceHistory.length > 0">
        <div class="history-title">{{ t('nearlysettingshistory') }}</div>
        <div class="history-item" v-for="item in preferenceHistory.slice(0, 4)" :key="item.saved_at">
          {{ new Date(item.saved_at).toLocaleString() }} - {{ item.frequency }} - {{ item.channels.join('/') }}
        </div>
      </div>
    </div>

    <el-skeleton v-if="loading && sortedNotifications.length === 0" :rows="4" animated />

    <div v-else class="notification-list">
      <article
        v-for="item in pageResult.list"
        :key="item.notification_id"
        class="notification-card"
        :class="[
          item.read ? 'is-read' : 'is-unread',
          `type-${item.type}`,
          `priority-${item.priority}`,
          selectedIdSet.has(item.notification_id) ? 'is-selected' : ''
        ]"
      >
        <div class="card-left" @click="toggleSelect(item.notification_id)">
          <input type="checkbox" :checked="selectedIdSet.has(item.notification_id)" />
          <span class="icon">{{ iconByType[item.type] }}</span>
        </div>
        <div class="card-main">
          <div class="card-title-line">
            <strong>{{ item.title }}</strong>
            <el-tag size="small" effect="plain">{{ item.source }}</el-tag>
            <el-tag size="small" :type="tagTypeByPriority[item.priority]">{{ item.priority }}</el-tag>
            <span class="time">{{ formatTime(item.created_at) }}</span>
          </div>
          <p class="content">{{ item.content }}</p>
          <div class="card-actions">
            <el-button text size="small" @click="openNotification(item)">{{ t('checkdetail') }}</el-button>
            <el-button text size="small" @click="toggleRead(item)">
              {{ item.read ? t('markasunread') : t('markasread') }}
            </el-button>
          </div>
        </div>
      </article>

      <div v-if="sortedNotifications.length === 0" class="empty">{{ t('nonoticeforthetime') }}</div>

      <div class="pagination-row" v-if="sortedNotifications.length > 0">
        <el-button size="small" @click="loadMore" :disabled="pageResult.currentPage >= pageResult.totalPages">
          {{ t('pulldowntoloadmore') }}
        </el-button>
        <el-pagination
          layout="prev, pager, next"
          :total="pageResult.total"
          :page-size="pageSize"
          :current-page="pageResult.currentPage"
          @current-change="onPageChange"
        />
      </div>
    </div>

    <transition-group name="toast" tag="div" class="toast-list">
      <div v-for="toast in toasts" :key="toast.id" class="toast-item" @mouseenter="toast.hover = true" @mouseleave="toast.hover = false">
        <div class="toast-title">{{ toast.title }}</div>
        <div class="toast-message">{{ toast.message }}</div>
        <div class="toast-actions">
          <button type="button" @click="openFromToast(toast)">{{ t('check') }}</button>
          <button type="button" @click="closeToast(toast.id)">{{ t('close') }}</button>
        </div>
      </div>
    </transition-group>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { ElMessage } from 'element-plus';
import { workflowRealtimeService } from '../../services/WorkflowRealtimeService';
import { workflowService } from '../../services/WorkflowService';
import {
  appendPreferenceHistory,
  countUnreadNotifications,
  createMockNotifications,
  filterNotifications,
  formatNotificationRelativeTime,
  markNotificationsRead,
  paginateNotifications,
  sortNotifications,
  upsertNotification,
  type NotificationPreferenceSnapshot,
  type WorkflowNotificationItem,
  type WorkflowNotificationPriority,
  type WorkflowNotificationType
} from './notificationCenterUtils';
import { useI18nText } from '../../i18n/useI18n';

const { t } = useI18nText();

interface WorkflowNotificationPreferences {
  types: Record<WorkflowNotificationType, boolean>;
  frequency: 'realtime' | '5m' | '15m' | 'daily';
  channels: Array<'popup' | 'list' | 'email'>;
}

interface NotificationToast {
  id: string;
  notificationId: string;
  title: string;
  message: string;
  hover: boolean;
}

const props = defineProps<{
  workflowId: string;
}>();

const loading = ref(false);
const notifications = ref<WorkflowNotificationItem[]>([]);
const page = ref(1);
const pageSize = 8;
const selectedIdSet = ref(new Set<string>());
const showSettings = ref(false);
const saveTip = ref(t('autosavestart'));
const toasts = ref<NotificationToast[]>([]);
let toastTimer: number | null = null;
let unsubRealtime: (() => void) | null = null;
let preferenceSaveTimer: number | null = null;

const filters = reactive<{
  singleType: 'all' | WorkflowNotificationType;
  multiTypes: WorkflowNotificationType[];
  sourceKeyword: string;
  textKeyword: string;
  unreadOnly: boolean;
}>({
  singleType: 'all',
  multiTypes: [],
  sourceKeyword: '',
  textKeyword: '',
  unreadOnly: false
});

const preferences = reactive<WorkflowNotificationPreferences>({
  types: {
    mention: true,
    comment: true,
    share: true,
    system: true
  },
  frequency: 'realtime',
  channels: ['popup', 'list']
});

const preferenceHistory = ref<NotificationPreferenceSnapshot[]>([]);

const sortBy = ref<'time' | 'type' | 'priority'>('time');
const groupByType = ref(false);
const unreadFirst = ref(true);

const storageKey = computed(() => `udake_workflow_notifications_${props.workflowId}`);
const settingStorageKey = computed(() => `udake_workflow_notification_settings_${props.workflowId}`);

const iconByType: Record<WorkflowNotificationType, string> = {
  mention: '@',
  comment: 'C',
  share: 'S',
  system: '!'
};

const tagTypeByPriority: Record<WorkflowNotificationPriority, 'success' | 'warning' | 'danger' | 'info'> = {
  low: 'info',
  normal: 'success',
  high: 'warning',
  urgent: 'danger'
};

const selectedIds = computed(() => Array.from(selectedIdSet.value));

const filteredNotifications = computed(() => {
  const allowedTypes = (Object.keys(preferences.types) as WorkflowNotificationType[]).filter((type) => preferences.types[type]);
  const list = notifications.value.filter((item) => allowedTypes.includes(item.type));
  return filterNotifications(list, filters);
});

const sortedNotifications = computed(() =>
  sortNotifications(filteredNotifications.value, {
    sortBy: sortBy.value,
    groupByType: groupByType.value,
    unreadFirst: unreadFirst.value
  })
);

const pageResult = computed(() => paginateNotifications(sortedNotifications.value, page.value, pageSize));
const unreadCount = computed(() => countUnreadNotifications(notifications.value));

function parseJSON<T>(raw: string | null, fallback: T): T {
  if (!raw) {
    return fallback;
  }
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function cacheNotifications() {
  localStorage.setItem(storageKey.value, JSON.stringify(notifications.value));
}

function cachePreferences() {
  const snapshot: NotificationPreferenceSnapshot = {
    saved_at: new Date().toISOString(),
    types: { ...preferences.types },
    channels: [...preferences.channels],
    frequency: preferences.frequency
  };

  preferenceHistory.value = appendPreferenceHistory(preferenceHistory.value, snapshot, 20);

  localStorage.setItem(
    settingStorageKey.value,
    JSON.stringify({
      preferences: {
        ...preferences,
        types: { ...preferences.types },
        channels: [...preferences.channels]
      },
      history: preferenceHistory.value
    })
  );
}

async function syncPreferenceToServer() {
  if (!props.workflowId) {
    return;
  }
  try {
    await workflowService.updateNotificationPreferences(props.workflowId, {
      types: preferences.types,
      channels: preferences.channels,
      frequency: preferences.frequency
    });
  } catch {
    // API 不可用时保留本地设置
  }
}

function schedulePreferenceSave() {
  if (preferenceSaveTimer !== null) {
    window.clearTimeout(preferenceSaveTimer);
  }
  preferenceSaveTimer = window.setTimeout(() => {
    cachePreferences();
    void syncPreferenceToServer();
    saveTip.value = `${t('autosavesuccess')} (${new Date().toLocaleTimeString()})`;
    ElMessage.success(t('noticesettingssavedsuccess'));
  }, 250);
}

function loadPreferences() {
  const payload = parseJSON<{
    preferences?: WorkflowNotificationPreferences;
    history?: NotificationPreferenceSnapshot[];
  }>(localStorage.getItem(settingStorageKey.value), {});

  if (payload.preferences) {
    preferences.types.mention = payload.preferences.types.mention;
    preferences.types.comment = payload.preferences.types.comment;
    preferences.types.share = payload.preferences.types.share;
    preferences.types.system = payload.preferences.types.system;
    preferences.frequency = payload.preferences.frequency;
    preferences.channels = payload.preferences.channels;
  }
  preferenceHistory.value = payload.history || [];
}

function resetFilters() {
  filters.singleType = 'all';
  filters.multiTypes = [];
  filters.sourceKeyword = '';
  filters.textKeyword = '';
  filters.unreadOnly = false;
}

function formatTime(value: string) {
  return formatNotificationRelativeTime(value, Date.now(), t);
}

function toggleSelect(notificationId: string) {
  const next = new Set(selectedIdSet.value);
  if (next.has(notificationId)) {
    next.delete(notificationId);
  } else {
    next.add(notificationId);
  }
  selectedIdSet.value = next;
}

function updateLocalNotification(item: WorkflowNotificationItem) {
  notifications.value = upsertNotification(notifications.value, item);
  cacheNotifications();
}

function upsertFromPayload(payload: Record<string, unknown>) {
  const type = String(payload.notification_type || payload.type || 'system') as WorkflowNotificationType;
  const supportedTypes: WorkflowNotificationType[] = ['mention', 'comment', 'share', 'system'];
  const normalizedType = supportedTypes.includes(type) ? type : 'system';

  const priority = String(payload.priority || 'normal') as WorkflowNotificationPriority;
  const supportedPriorities: WorkflowNotificationPriority[] = ['low', 'normal', 'high', 'urgent'];
  const normalizedPriority = supportedPriorities.includes(priority) ? priority : 'normal';

  const next: WorkflowNotificationItem = {
    notification_id: String(payload.notification_id || `rt_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`),
    workflow_id: props.workflowId,
    type: normalizedType,
    title: String(payload.title || t('newnotice')),
    content: String(payload.content || payload.message || ''),
    source: String(payload.source || t('intimeissue')),
    source_id: payload.source_id ? String(payload.source_id) : undefined,
    created_at: typeof payload.created_at === 'string' ? payload.created_at : new Date().toISOString(),
    priority: normalizedPriority,
    read: false,
    metadata: {
      ...payload
    }
  };

  updateLocalNotification(next);
  if (preferences.channels.includes('popup')) {
    pushToast(next);
  }
}

function pushToast(notification: WorkflowNotificationItem) {
  const toast: NotificationToast = {
    id: `toast_${notification.notification_id}`,
    notificationId: notification.notification_id,
    title: notification.title,
    message: notification.content,
    hover: false
  };
  toasts.value = [toast, ...toasts.value].slice(0, 5);

  if (toastTimer !== null) {
    window.clearTimeout(toastTimer);
  }
  toastTimer = window.setTimeout(() => {
    const stale = toasts.value.filter((item) => !item.hover);
    if (stale.length > 0) {
      closeToast(stale[stale.length - 1].id);
    }
  }, 3200);
}

function closeToast(id: string) {
  toasts.value = toasts.value.filter((toast) => toast.id !== id);
}

function openFromToast(toast: NotificationToast) {
  const target = notifications.value.find((item) => item.notification_id === toast.notificationId);
  if (target) {
    openNotification(target);
  }
  closeToast(toast.id);
}

function openNotification(item: WorkflowNotificationItem) {
  if (!item.read) {
    void markSingleAsRead(item.notification_id);
  }
  if (item.source_id) {
    window.dispatchEvent(
      new CustomEvent('workflow-notification-open', {
        detail: {
          notificationId: item.notification_id,
          sourceId: item.source_id,
          workflowId: props.workflowId,
          type: item.type
        }
      })
    );
  }
}

async function markSingleAsRead(notificationId: string) {
  notifications.value = markNotificationsRead(notifications.value, [notificationId], true);
  selectedIdSet.value.delete(notificationId);
  selectedIdSet.value = new Set(selectedIdSet.value);
  cacheNotifications();

  try {
    await workflowService.markNotificationRead(props.workflowId, notificationId);
  } catch {
    // 本地优先
  }
}

function toggleRead(item: WorkflowNotificationItem) {
  const nextRead = !item.read;
  notifications.value = markNotificationsRead(notifications.value, [item.notification_id], nextRead);
  cacheNotifications();
  if (nextRead) {
    void workflowService.markNotificationRead(props.workflowId, item.notification_id).catch(() => undefined);
  }
}

async function markSelectedAsRead() {
  const ids = selectedIds.value;
  if (ids.length === 0) {
    return;
  }
  notifications.value = markNotificationsRead(notifications.value, ids, true);
  selectedIdSet.value = new Set();
  cacheNotifications();

  try {
    await workflowService.batchMarkNotificationsRead(props.workflowId, ids);
  } catch {
    // 本地优先
  }
}

async function markAllAsRead() {
  notifications.value = markNotificationsRead(notifications.value, 'all', true);
  selectedIdSet.value = new Set();
  cacheNotifications();
  try {
    await workflowService.markAllNotificationsRead(props.workflowId);
  } catch {
    // 本地优先
  }
}

async function fetchNotifications(reset = false) {
  if (!props.workflowId) {
    return;
  }
  if (reset) {
    page.value = 1;
  }
  loading.value = true;

  try {
    const data = await workflowService.listNotifications(props.workflowId, {
      page: 1,
      page_size: 200,
      sort: 'desc'
    });

    if (data.notifications.length > 0) {
      notifications.value = data.notifications;
    } else {
      notifications.value = parseJSON<WorkflowNotificationItem[]>(localStorage.getItem(storageKey.value), []);
      if (notifications.value.length === 0) {
        notifications.value = createMockNotifications(props.workflowId);
      }
    }
  } catch {
    notifications.value = parseJSON<WorkflowNotificationItem[]>(localStorage.getItem(storageKey.value), []);
    if (notifications.value.length === 0) {
      notifications.value = createMockNotifications(props.workflowId);
    }
  } finally {
    cacheNotifications();
    loading.value = false;
  }
}

function onPageChange(nextPage: number) {
  page.value = nextPage;
}

function loadMore() {
  if (page.value < pageResult.value.totalPages) {
    page.value += 1;
  }
}

function refreshNotifications() {
  return fetchNotifications(true);
}

function attachRealtime() {
  workflowRealtimeService.start();
  workflowRealtimeService.setWorkflowSubscription(props.workflowId);
  unsubRealtime = workflowRealtimeService.subscribe((event) => {
    const eventType = event.type.toLowerCase();
    if (eventType.includes('notification')) {
      upsertFromPayload(event.payload);
      return;
    }
    if (eventType.includes('comment') || eventType.includes('mention') || eventType.includes('share')) {
      const titleMap: Record<string, string> = {
        comment: t('newcommentnotice'),
        mention: t('mentionnotice'),
        share: t('sharenotice')
      };
      const normalized = eventType.includes('mention')
        ? 'mention'
        : eventType.includes('share')
          ? 'share'
          : 'comment';
      upsertFromPayload({
        notification_id: `rt_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
        notification_type: normalized,
        title: titleMap[normalized],
        content: String(event.payload.message || event.payload.content || t('recievecomessage')),
        source: t('intimeco'),
        priority: normalized === 'mention' ? 'high' : 'normal',
        created_at: new Date().toISOString(),
        source_id: String(event.payload.comment_id || '')
      });
    }
  });
}

function handleLocalPush(event: Event) {
  const custom = event as CustomEvent<Record<string, unknown>>;
  const detail = custom.detail || {};
  upsertFromPayload(detail);
}

watch(
  () => props.workflowId,
  (workflowId) => {
    if (!workflowId) {
      notifications.value = [];
      return;
    }
    selectedIdSet.value = new Set();
    void fetchNotifications(true);
    workflowRealtimeService.setWorkflowSubscription(workflowId);
  },
  { immediate: true }
);

watch(
  () => [
    preferences.types.mention,
    preferences.types.comment,
    preferences.types.share,
    preferences.types.system,
    preferences.frequency,
    preferences.channels.join(',')
  ],
  () => {
    schedulePreferenceSave();
  }
);

watch(
  () => [filters.singleType, filters.multiTypes.length, filters.sourceKeyword, filters.textKeyword, filters.unreadOnly],
  () => {
    page.value = 1;
  }
);

onMounted(() => {
  loadPreferences();
  attachRealtime();
  window.addEventListener('workflow-notification-push', handleLocalPush as EventListener);
});

onBeforeUnmount(() => {
  if (toastTimer !== null) {
    window.clearTimeout(toastTimer);
    toastTimer = null;
  }
  if (preferenceSaveTimer !== null) {
    window.clearTimeout(preferenceSaveTimer);
    preferenceSaveTimer = null;
  }
  if (unsubRealtime) {
    unsubRealtime();
    unsubRealtime = null;
  }
  window.removeEventListener('workflow-notification-push', handleLocalPush as EventListener);
});
</script>

<style scoped>
.notification-center {
  border: 1px solid #dde5f3;
  border-radius: 12px;
  background: #fff;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.notification-header {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: center;
}

.title-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.title-wrap h3 {
  margin: 0;
  font-size: 16px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.quick-filter-row,
.advanced-filter-row,
.sort-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.settings-panel {
  border: 1px solid #e7edf8;
  border-radius: 10px;
  background: linear-gradient(180deg, #fbfcff 0%, #f7f9ff 100%);
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.settings-panel h4 {
  margin: 0;
  font-size: 14px;
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.settings-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.settings-row .label {
  width: 72px;
  color: #51607a;
  font-size: 12px;
}

.save-tip {
  color: #2f855a;
  font-size: 12px;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.history-title {
  font-size: 12px;
  color: #51607a;
}

.history-item {
  font-size: 12px;
  color: #6b7280;
}

.notification-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.notification-card {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 10px;
  border: 1px solid #e5ecf6;
  border-radius: 10px;
  padding: 10px;
  transition: all 0.2s ease;
}

.notification-card.is-unread {
  background: linear-gradient(90deg, #edf4ff 0%, #ffffff 22%);
  border-left: 4px solid #3b82f6;
}

.notification-card.is-selected {
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.22);
}

.card-left {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.icon {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  background: #eaf2ff;
  color: #1d4ed8;
}

.card-title-line {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.card-title-line .time {
  margin-left: auto;
  color: #77839b;
  font-size: 12px;
}

.content {
  margin: 6px 0;
  color: #273449;
  line-height: 1.45;
}

.card-actions {
  display: flex;
  gap: 4px;
}

.empty {
  text-align: center;
  color: #8a94a8;
  padding: 24px 0;
}

.pagination-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}

.toast-list {
  position: fixed;
  top: 90px;
  right: 18px;
  z-index: 1200;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.toast-item {
  width: min(320px, calc(100vw - 32px));
  border-radius: 10px;
  background: rgba(17, 24, 39, 0.92);
  color: #fff;
  padding: 10px;
  box-shadow: 0 14px 32px rgba(0, 0, 0, 0.32);
}

.toast-title {
  font-size: 13px;
  font-weight: 600;
}

.toast-message {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.4;
  color: #e2e8f0;
}

.toast-actions {
  margin-top: 8px;
  display: flex;
  gap: 6px;
}

.toast-actions button {
  border: none;
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 12px;
  cursor: pointer;
}

.toast-actions button:first-child {
  background: #2563eb;
  color: #fff;
}

.toast-actions button:last-child {
  background: #d1d5db;
  color: #111827;
}

.toast-enter-active,
.toast-leave-active {
  transition: all 0.25s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateX(20px) translateY(-6px);
}

@media (max-width: 768px) {
  .notification-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .settings-grid {
    grid-template-columns: 1fr;
  }

  .toast-list {
    right: 10px;
    top: 78px;
  }
}
</style>
