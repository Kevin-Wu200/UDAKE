<template>
  <section class="comment-thread">
    <header class="comment-header">
      <div class="header-main">
        <h3>{{ t('commentthread') }}</h3>
        <el-tag size="small" effect="plain">{{ totalCount }} {{ t('pieces') }}</el-tag>
        <el-tag v-if="mentionCount > 0" size="small" type="warning" effect="plain">{{ t('me') }} {{ mentionCount }}</el-tag>
      </div>
      <div class="header-actions">
        <el-switch v-model="settingsEnabled" inline-prompt :active-text="t('notice')" :inactive-text="t('quiet')" />
        <el-button text @click="toggleSettings">{{ t('settings') }}</el-button>
        <el-button text @click="toggleBatchMode">{{ batchMode ? t('quitbatchoperation') : t('batchoperation') }}</el-button>
      </div>
    </header>

    <div v-if="showSettings" class="settings-panel">
      <el-switch v-model="settings.enableNewComment" :active-text="t('newcomment')" />
      <el-switch v-model="settings.enableMention" :active-text="t('mention')" />
      <el-switch v-model="settings.enableReply" :active-text="t('answer')" />
      <el-switch v-model="settings.doNotDisturb" :active-text="t('nodisturb')" />
      <el-select v-model="settings.frequency" size="small" style="width: 120px">
        <el-option :label="t('intime')" value="realtime" />
        <el-option :label="`${30} ${t('sc')}`" value="30s" />
        <el-option :label="`${60} ${t('sc')}`" value="60s" />
      </el-select>
      <el-button size="small" @click="saveSettings">{{ t('savesettings') }}</el-button>
    </div>

    <div class="composer-card">
      <div v-if="replyingTo" class="replying-banner">
        {{ t('answering') }} {{ replyingTo.author_name }}
        <el-button link type="primary" @click="cancelReply">{{ t('cancel') }}</el-button>
      </div>
      <el-input
        ref="composerRef"
        v-model="composer"
        type="textarea"
        :rows="4"
        resize="vertical"
        :placeholder="t('addcomment')"
        @input="onComposerInput"
        @keydown="onComposerKeydown"
      />

      <div v-if="mentionPanelVisible" class="mention-panel">
        <div
          v-for="(user, index) in mentionCandidates"
          :key="user.user_id"
          class="mention-item"
          :class="{ active: index === mentionActiveIndex }"
          @mousedown.prevent="applyMention(user)"
        >
          <div class="name-line">
            <span>{{ user.display_name }}</span>
            <span class="muted">@{{ user.user_id }}</span>
          </div>
          <span class="muted">{{ t('mentionwithoutat') + ' ' + user.mention_count + ' ' + t('times')}}</span>
        </div>
      </div>

      <div class="composer-actions">
        <el-button size="small" @click="previewVisible = !previewVisible">{{ previewVisible ? t('hidepreview') : t('preview') }}</el-button>
        <el-button type="primary" :loading="submitting" :disabled="!composer.trim()" @click="submitComment">{{ t('submitcomment') }}</el-button>
      </div>

      <div v-if="previewVisible" class="preview-box" v-html="renderHighlighted(composer)"></div>
    </div>

    <div class="list-toolbar">
      <el-radio-group v-model="sortOrder" size="small" @change="refreshComments">
        <el-radio-button label="asc">{{ t('timesequence') }}</el-radio-button>
        <el-radio-button label="desc">{{ t('timereverseorder') }}</el-radio-button>
      </el-radio-group>
      <el-button size="small" @click="refreshComments" :loading="loading">{{ t('refresh') }}</el-button>
      <el-button
        v-if="batchMode"
        size="small"
        type="danger"
        :disabled="selectedCommentIds.length === 0"
        @click="batchDelete"
      >
        {{ t('batchdeletion') }} ({{ selectedCommentIds.length }})
      </el-button>
    </div>

    <el-skeleton v-if="loading && displayRoots.length === 0" :rows="4" animated />

    <div v-else class="comment-list">
      <template v-for="item in displayRoots" :key="item.comment_id">
        <CommentItem
          :item="item"
          :batch-mode="batchMode"
          :selected-ids="selectedCommentIds"
          :current-user-id="currentUserId"
          :is-admin="isAdmin"
          :collapsed-map="collapsedMap"
          @reply="startReply"
          @edit="startEdit"
          @delete="deleteComment"
          @save-edit="saveEdit"
          @cancel-edit="cancelEdit"
          @toggle-collapse="toggleCollapse"
          @toggle-select="toggleSelect"
          @jump-mention="jumpToUser"
        />
      </template>
      <div class="load-more">
        <el-button v-if="hasMore" size="small" :loading="loadingMore" @click="loadMore">{{ t('loadmore') }}</el-button>
        <span v-else class="muted">{{ t('allcommentloaded') }}</span>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { ElMessage, ElMessageBox, ElNotification } from 'element-plus';
import { workflowRealtimeService } from '../../services/WorkflowRealtimeService';
import { workflowService } from '../../services/WorkflowService';
import type { WorkflowComment, WorkflowCommentMention } from '../../types/workflow';
import { useI18nText } from '../../i18n/useI18n';

interface MentionCandidate {
  user_id: string;
  display_name: string;
  mention_count: number;
}

interface CommentTreeItem extends WorkflowComment {
  children: CommentTreeItem[];
  display_depth: number;
  reply_to_name: string;
  editing: boolean;
  edit_content: string;
}

interface NotificationSettings {
  enableNewComment: boolean;
  enableMention: boolean;
  enableReply: boolean;
  doNotDisturb: boolean;
  frequency: 'realtime' | '30s' | '60s';
}

const props = withDefaults(
  defineProps<{
    workflowId: string;
    currentUserId: string;
    currentUserName: string;
    isAdmin?: boolean;
  }>(),
  {
    isAdmin: false
  }
);

const COMMENT_CACHE_PREFIX = 'udake_workflow_comment_cache_';
const SETTING_CACHE_PREFIX = 'udake_workflow_comment_settings_';
const { t } = useI18nText();

const composerRef = ref();
const composer = ref('');
const previewVisible = ref(false);
const replyingTo = ref<CommentTreeItem | null>(null);
const loading = ref(false);
const loadingMore = ref(false);
const submitting = ref(false);
const sortOrder = ref<'asc' | 'desc'>('asc');
const comments = ref<WorkflowComment[]>([]);
const page = ref(1);
const pageSize = 20;
const hasMore = ref(false);
const totalCount = ref(0);
const knownCommentIds = ref(new Set<string>());
const pollTimer = ref<number | null>(null);
const unsubRealtime = ref<(() => void) | null>(null);

const showSettings = ref(false);
const settingsEnabled = ref(true);
const settings = reactive<NotificationSettings>({
  enableNewComment: true,
  enableMention: true,
  enableReply: true,
  doNotDisturb: false,
  frequency: 'realtime'
});

const batchMode = ref(false);
const selectedCommentIds = ref<string[]>([]);
const collapsedMap = reactive<Record<string, boolean>>({});

const mentionPanelVisible = ref(false);
const mentionCandidates = ref<MentionCandidate[]>([]);
const mentionActiveIndex = ref(0);
const mentionQuery = ref('');
const mentionStartIndex = ref(-1);

const mentionStatsMap = computed(() => {
  const map = new Map<string, number>();
  comments.value.forEach((comment) => {
    const mentions = resolveMentions(comment.content, comment.mention_users);
    mentions.forEach((m) => {
      map.set(m.display_name, (map.get(m.display_name) || 0) + 1);
    });
  });
  return map;
});

const mentionCount = computed(() => {
  return comments.value.filter((comment) => {
    if (comment.deleted) {
      return false;
    }
    const mentions = resolveMentions(comment.content, comment.mention_users);
    return mentions.some((m) => m.user_id === props.currentUserId || m.display_name === props.currentUserName);
  }).length;
});

function parseCache<T>(raw: string | null, fallback: T): T {
  if (!raw) {
    return fallback;
  }
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function commentCacheKey() {
  return `${COMMENT_CACHE_PREFIX}${props.workflowId}`;
}

function settingCacheKey() {
  return `${SETTING_CACHE_PREFIX}${props.workflowId}`;
}

function saveSettings() {
  localStorage.setItem(
    settingCacheKey(),
    JSON.stringify({
      ...settings,
      settingsEnabled: settingsEnabled.value
    })
  );
  syncPolling();
  ElMessage.success(t('commentnoticesettingssavedsuccess'));
}

function loadSettings() {
  const raw = parseCache<NotificationSettings & { settingsEnabled?: boolean }>(
    localStorage.getItem(settingCacheKey()),
    {
      ...settings,
      settingsEnabled: true
    }
  );
  settings.enableNewComment = raw.enableNewComment;
  settings.enableMention = raw.enableMention;
  settings.enableReply = raw.enableReply;
  settings.doNotDisturb = raw.doNotDisturb;
  settings.frequency = raw.frequency;
  settingsEnabled.value = raw.settingsEnabled !== false;
}

function saveCommentCache() {
  localStorage.setItem(
    commentCacheKey(),
    JSON.stringify({
      comments: comments.value,
      count: totalCount.value,
      updated_at: new Date().toISOString()
    })
  );
}

function loadCommentCache() {
  const raw = parseCache<{ comments: WorkflowComment[]; count: number }>(
    localStorage.getItem(commentCacheKey()),
    {
      comments: [],
      count: 0
    }
  );
  comments.value = raw.comments;
  totalCount.value = raw.count;
  knownCommentIds.value = new Set(raw.comments.map((c) => c.comment_id));
}

function normalizeComments(incoming: WorkflowComment[]) {
  const seen = new Set<string>();
  const ordered = [...incoming]
    .filter((item) => {
      if (!item.comment_id || seen.has(item.comment_id)) {
        return false;
      }
      seen.add(item.comment_id);
      return true;
    })
    .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());

  comments.value = sortOrder.value === 'asc' ? ordered : [...ordered].reverse();
  totalCount.value = comments.value.length;
  saveCommentCache();
}

async function fetchFromApi(reset = false) {
  if (!props.workflowId) {
    return;
  }

  if (reset) {
    page.value = 1;
  }

  const requestPage = page.value;
  if (requestPage === 1) {
    loading.value = true;
  } else {
    loadingMore.value = true;
  }

  try {
    const data = await workflowService.listComments(props.workflowId, {
      page: requestPage,
      page_size: pageSize,
      sort: sortOrder.value
    });

    const merged = requestPage === 1 ? data.comments : [...comments.value, ...data.comments];
    normalizeComments(merged);
    hasMore.value = Boolean(data.has_more) || comments.value.length < data.count;
    totalCount.value = data.count;

    if (requestPage === 1) {
      notifyForNewComments(data.comments);
      knownCommentIds.value = new Set(data.comments.map((item) => item.comment_id));
    } else {
      data.comments.forEach((item) => knownCommentIds.value.add(item.comment_id));
    }

    saveCommentCache();
  } catch {
    if (comments.value.length === 0) {
      loadCommentCache();
      hasMore.value = false;
    }
  } finally {
    loading.value = false;
    loadingMore.value = false;
  }
}

function notifyForNewComments(incoming: WorkflowComment[]) {
  if (!settingsEnabled.value || settings.doNotDisturb) {
    return;
  }

  const newItems = incoming.filter((item) => !knownCommentIds.value.has(item.comment_id));
  newItems.forEach((item) => {
    const mentions = resolveMentions(item.content, item.mention_users);
    const mentionedCurrent = mentions.some(
      (m) => m.user_id === props.currentUserId || m.display_name === props.currentUserName
    );
    const replyCurrent = item.parent_id
      ? comments.value.some((c) => c.comment_id === item.parent_id && c.author_id === props.currentUserId)
      : false;

    if (mentionedCurrent && settings.enableMention) {
      emitNotificationPush(item, 'mention', `${t('mentionnotice')}`, `${item.author_name} ${t('mentionedincomment')}`, 'high');
      ElNotification({
        title: t('mentionnotice'),
        message: `${item.author_name} ${t('mentionedincomment')}`,
        duration: 2800,
        onClick: () => scrollToComment(item.comment_id)
      });
      return;
    }

    if (replyCurrent && settings.enableReply) {
      emitNotificationPush(item, 'comment', t('replynotice'), `${item.author_name} ${t('replycomment')}`, 'high');
      ElNotification({
        title: t('replynotice'),
        message: `${item.author_name} ${t('replycomment')}`,
        duration: 2800,
        onClick: () => scrollToComment(item.comment_id)
      });
      return;
    }

    if (settings.enableNewComment) {
      emitNotificationPush(item, 'comment', t('newcomment'), `${item.author_name}: ${truncate(item.content, 32)}`, 'normal');
      ElNotification({
        title: t('newcomment'),
        message: `${item.author_name}: ${truncate(item.content, 32)}`,
        duration: 2200,
        onClick: () => scrollToComment(item.comment_id)
      });
    }
  });
}

function truncate(text: string, size: number) {
  if (text.length <= size) {
    return text;
  }
  return `${text.slice(0, size)}...`;
}

function emitNotificationPush(
  item: WorkflowComment,
  type: 'mention' | 'comment' | 'share' | 'system',
  title: string,
  message: string,
  priority: 'low' | 'normal' | 'high' | 'urgent'
) {
  window.dispatchEvent(
    new CustomEvent('workflow-notification-push', {
      detail: {
        notification_id: `comment_${item.comment_id}`,
        workflow_id: props.workflowId,
        notification_type: type,
        title,
        content: message,
        source: t('commentthread'),
        source_id: item.comment_id,
        priority,
        created_at: item.created_at
      }
    })
  );
}

function toggleSettings() {
  showSettings.value = !showSettings.value;
}

function toggleBatchMode() {
  batchMode.value = !batchMode.value;
  if (!batchMode.value) {
    selectedCommentIds.value = [];
  }
}

function toggleSelect(commentId: string) {
  const set = new Set(selectedCommentIds.value);
  if (set.has(commentId)) {
    set.delete(commentId);
  } else {
    set.add(commentId);
  }
  selectedCommentIds.value = Array.from(set);
}

async function batchDelete() {
  if (!selectedCommentIds.value.length) {
    return;
  }

  try {
    await ElMessageBox.confirm(`${t('confirmdelete')} ${selectedCommentIds.value.length} ${t('askforthiscomment')}`, t('confirmbatchdelete'), {
      confirmButtonText: t('delete'),
      cancelButtonText: t('cancel'),
      type: 'warning'
    });
  } catch {
    return;
  }

  try {
    await workflowService.batchDeleteComments(props.workflowId, selectedCommentIds.value);
    ElMessage.success(t('batchdeletefinish'));
  } catch {
    // 兼容无批量接口，改为串行删除
    await Promise.all(
      selectedCommentIds.value.map(async (id) => {
        try {
          await workflowService.deleteComment(props.workflowId, id);
        } catch {
          // 忽略单条失败
        }
      })
    );
  }

  selectedCommentIds.value = [];
  await refreshComments();
}

function resolveMentions(content: string, mentionUsers: WorkflowCommentMention[]) {
  if (mentionUsers.length > 0) {
    return mentionUsers;
  }

  const byName = Array.from(content.matchAll(/@([\u4e00-\u9fa5A-Za-z0-9_\-.]+)/g)).map((item) => item[1]);
  return byName.map((name) => ({
    user_id: name,
    display_name: name
  }));
}

function renderHighlighted(content: string) {
  const escaped = content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

  const mentionPattern = /@([\u4e00-\u9fa5A-Za-z0-9_\-.]+)/g;
  const withMention = escaped.replace(mentionPattern, '<span class="mention">@$1</span>');
  return withMention.replace(/\n/g, '<br/>');
}

function onComposerInput() {
  const textarea = composerRef.value?.textarea as HTMLTextAreaElement | undefined;
  if (!textarea) {
    mentionPanelVisible.value = false;
    return;
  }

  const cursor = textarea.selectionStart || 0;
  const leftText = composer.value.slice(0, cursor);
  const match = leftText.match(/(?:^|\s)@([\u4e00-\u9fa5A-Za-z0-9_\-.]{0,20})$/);
  if (!match) {
    mentionPanelVisible.value = false;
    mentionQuery.value = '';
    mentionStartIndex.value = -1;
    return;
  }

  mentionQuery.value = match[1] || '';
  mentionStartIndex.value = cursor - match[1].length - 1;
  mentionPanelVisible.value = true;
  mentionActiveIndex.value = 0;
  void loadMentionCandidates(mentionQuery.value);
}

function onComposerKeydown(event: Event | KeyboardEvent) {
  if (!(event instanceof KeyboardEvent)) {
    return;
  }
  if (!mentionPanelVisible.value || mentionCandidates.value.length === 0) {
    return;
  }

  if (event.key === 'ArrowDown') {
    event.preventDefault();
    mentionActiveIndex.value = (mentionActiveIndex.value + 1) % mentionCandidates.value.length;
    return;
  }

  if (event.key === 'ArrowUp') {
    event.preventDefault();
    mentionActiveIndex.value =
      (mentionActiveIndex.value - 1 + mentionCandidates.value.length) % mentionCandidates.value.length;
    return;
  }

  if (event.key === 'Enter') {
    event.preventDefault();
    applyMention(mentionCandidates.value[mentionActiveIndex.value]);
    return;
  }

  if (event.key === 'Escape') {
    mentionPanelVisible.value = false;
  }
}

async function loadMentionCandidates(keyword: string) {
  const localUsers = buildLocalMentionCandidates(keyword);
  mentionCandidates.value = localUsers;

  if (!props.workflowId) {
    return;
  }

  try {
    const data = await workflowService.searchMentionCandidates(props.workflowId, keyword);
    const normalized = data.users.map((user) => ({
      user_id: user.user_id,
      display_name: user.display_name || user.user_id,
      mention_count: mentionStatsMap.value.get(user.display_name || user.user_id) || 0
    }));
    mentionCandidates.value = normalized.length > 0 ? normalized : localUsers;
  } catch {
    // 使用本地候选
  }
}

function buildLocalMentionCandidates(keyword: string) {
  const map = new Map<string, MentionCandidate>();
  const append = (userId: string, displayName: string) => {
    const normalizedName = displayName || userId;
    const key = userId || normalizedName;
    if (!key) {
      return;
    }

    map.set(key, {
      user_id: userId || normalizedName,
      display_name: normalizedName,
      mention_count: mentionStatsMap.value.get(normalizedName) || 0
    });
  };

  append(props.currentUserId, props.currentUserName);
  comments.value.forEach((comment) => {
    append(comment.author_id, comment.author_name);
    resolveMentions(comment.content, comment.mention_users).forEach((m) => append(m.user_id, m.display_name));
  });

  const normalizedKeyword = keyword.trim().toLowerCase();
  return Array.from(map.values())
    .filter((item) => {
      if (!normalizedKeyword) {
        return true;
      }
      return (
        item.display_name.toLowerCase().includes(normalizedKeyword) ||
        item.user_id.toLowerCase().includes(normalizedKeyword)
      );
    })
    .sort((a, b) => b.mention_count - a.mention_count)
    .slice(0, 8);
}

function applyMention(user: MentionCandidate) {
  const textarea = composerRef.value?.textarea as HTMLTextAreaElement | undefined;
  if (!textarea || mentionStartIndex.value < 0) {
    return;
  }

  const cursor = textarea.selectionStart || 0;
  const before = composer.value.slice(0, mentionStartIndex.value);
  const after = composer.value.slice(cursor);
  composer.value = `${before}@${user.display_name} ${after}`;

  mentionPanelVisible.value = false;
  mentionQuery.value = '';
  mentionStartIndex.value = -1;

  nextTick(() => {
    const pos = before.length + user.display_name.length + 2;
    textarea.focus();
    textarea.setSelectionRange(pos, pos);
  });
}

function findMentionsFromComposer() {
  const candidates = buildLocalMentionCandidates('');
  const mentions = Array.from(composer.value.matchAll(/@([\u4e00-\u9fa5A-Za-z0-9_\-.]+)/g)).map((m) => m[1]);
  const mentionUsers: WorkflowCommentMention[] = [];

  mentions.forEach((name) => {
    const found = candidates.find((item) => item.display_name === name || item.user_id === name);
    if (found) {
      mentionUsers.push({
        user_id: found.user_id,
        display_name: found.display_name
      });
    }
  });

  return mentionUsers;
}

function startReply(item: CommentTreeItem) {
  replyingTo.value = item;
  composerRef.value?.focus?.();
}

function cancelReply() {
  replyingTo.value = null;
}

async function submitComment() {
  const content = composer.value.trim();
  if (!content) {
    return;
  }

  submitting.value = true;
  const mentionUsers = findMentionsFromComposer();
  const optimisticId = `local_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`;
  const nowIso = new Date().toISOString();

  const optimisticComment: WorkflowComment = {
    comment_id: optimisticId,
    workflow_id: props.workflowId,
    parent_id: replyingTo.value?.comment_id || null,
    root_id: replyingTo.value?.root_id || replyingTo.value?.comment_id || null,
    depth: (replyingTo.value?.depth || 0) + (replyingTo.value ? 1 : 0),
    content,
    created_at: nowIso,
    updated_at: nowIso,
    deleted: false,
    author_id: props.currentUserId,
    author_name: props.currentUserName,
    mention_users: mentionUsers,
    reply_count: 0
  };

  normalizeComments([...comments.value, optimisticComment]);
  composer.value = '';
  replyingTo.value = null;
  previewVisible.value = false;

  try {
    const created = await workflowService.createComment(props.workflowId, {
      content,
      parent_id: optimisticComment.parent_id,
      mention_user_ids: mentionUsers.map((m) => m.user_id)
    });

    normalizeComments(
      comments.value.map((item) => (item.comment_id === optimisticId ? created : item))
    );
    ElMessage.success(t('commentpublished'));
  } catch {
    ElMessage.warning(t('commentnointernet'));
  } finally {
    submitting.value = false;
  }
}

function canEdit(item: CommentTreeItem) {
  return !item.deleted && item.author_id === props.currentUserId;
}

function canDelete(item: CommentTreeItem) {
  return !item.deleted && (item.author_id === props.currentUserId || props.isAdmin);
}

function startEdit(item: CommentTreeItem) {
  if (!canEdit(item)) {
    return;
  }
  item.editing = true;
  item.edit_content = item.content;
}

function cancelEdit(item: CommentTreeItem) {
  item.editing = false;
  item.edit_content = item.content;
}

async function saveEdit(item: CommentTreeItem) {
  const next = item.edit_content.trim();
  if (!next) {
    return;
  }

  const previous = item.content;
  item.content = next;
  item.editing = false;

  normalizeComments(
    comments.value.map((comment) =>
      comment.comment_id === item.comment_id
        ? {
            ...comment,
            content: next,
            updated_at: new Date().toISOString()
          }
        : comment
    )
  );

  try {
    await workflowService.updateComment(props.workflowId, item.comment_id, {
      content: next
    });
    ElMessage.success(t('commentrefresh'));
  } catch {
    item.content = previous;
    normalizeComments(
      comments.value.map((comment) =>
        comment.comment_id === item.comment_id
          ? {
              ...comment,
              content: previous
            }
          : comment
      )
    );
    ElMessage.error(t('editfailed'));
  }
}

async function deleteComment(item: CommentTreeItem) {
  if (!canDelete(item)) {
    ElMessage.warning(t('nodeleteright'));
    return;
  }

  try {
    await ElMessageBox.confirm(t('commentdeleteconfirm'), t('deleteconfirm'), {
      confirmButtonText: t('delete'),
      cancelButtonText: t('cancel'),
      type: 'warning'
    });
  } catch {
    return;
  }

  const next = comments.value.map((comment) =>
    comment.comment_id === item.comment_id
      ? {
          ...comment,
          deleted: true,
          content: t('commentdeleted')
        }
      : comment
  );
  normalizeComments(next);

  try {
    await workflowService.deleteComment(props.workflowId, item.comment_id);
    ElMessage.success(t('commentdeletesuccess'));
  } catch {
    ElMessage.warning(t('deleteRequestfailed'));
  }
}

function toggleCollapse(commentId: string) {
  collapsedMap[commentId] = !collapsedMap[commentId];
}

function toTreeItems(source: WorkflowComment[]) {
  const map = new Map<string, CommentTreeItem>();
  source.forEach((comment) => {
    map.set(comment.comment_id, {
      ...comment,
      children: [],
      display_depth: 0,
      reply_to_name: '',
      editing: false,
      edit_content: comment.content
    });
  });

  const roots: CommentTreeItem[] = [];
  source.forEach((comment) => {
    const current = map.get(comment.comment_id);
    if (!current) {
      return;
    }

    const parent = comment.parent_id ? map.get(comment.parent_id) : null;
    if (!parent) {
      current.display_depth = 0;
      roots.push(current);
      return;
    }

    const nextDepth = Math.min(parent.display_depth + 1, 2);
    current.display_depth = nextDepth;
    current.reply_to_name = parent.author_name;

    // 超过三层统一平铺到第三层，避免结构过深
    if (parent.display_depth >= 2) {
      const topParent = parent;
      topParent.children.push(current);
      return;
    }

    parent.children.push(current);
  });

  const sortFn = (a: CommentTreeItem, b: CommentTreeItem) => {
    const diff = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
    return sortOrder.value === 'asc' ? diff : -diff;
  };

  const sortRecursive = (list: CommentTreeItem[]) => {
    list.sort(sortFn);
    list.forEach((item) => sortRecursive(item.children));
  };

  sortRecursive(roots);

  roots.forEach((root) => {
    root.children.forEach((child) => {
      if (child.children.length > 2 && collapsedMap[child.comment_id] === undefined) {
        collapsedMap[child.comment_id] = true;
      }
    });
  });

  return roots;
}

const displayRoots = computed(() => toTreeItems(comments.value));

function refreshComments() {
  return fetchFromApi(true);
}

function loadMore() {
  if (!hasMore.value || loadingMore.value) {
    return;
  }
  page.value += 1;
  return fetchFromApi(false);
}

function scrollToComment(commentId: string) {
  nextTick(() => {
    const el = document.querySelector(`[data-comment-id="${commentId}"]`) as HTMLElement | null;
    if (!el) {
      return;
    }
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    el.classList.add('jump-highlight');
    window.setTimeout(() => {
      el.classList.remove('jump-highlight');
    }, 1400);
  });
}

function jumpToUser(displayName: string) {
  ElMessage.info(`${t('mentionuser')}${displayName}`);
}

function syncPolling() {
  if (pollTimer.value !== null) {
    window.clearInterval(pollTimer.value);
    pollTimer.value = null;
  }

  if (!settingsEnabled.value) {
    return;
  }

  if (settings.frequency === 'realtime') {
    return;
  }

  const interval = settings.frequency === '30s' ? 30_000 : 60_000;
  pollTimer.value = window.setInterval(() => {
    void fetchFromApi(true);
  }, interval);
}

function attachRealtime() {
  workflowRealtimeService.start();
  workflowRealtimeService.setWorkflowSubscription(props.workflowId);
  unsubRealtime.value = workflowRealtimeService.subscribe((event) => {
    const type = event.type;
    if (type.includes('comment') || type.includes('mention') || type.includes('reply')) {
      void fetchFromApi(true);
    }
  });
}

function handleMentionShortcut(event: Event) {
  const custom = event as CustomEvent<{ userId?: string; displayName?: string }>;
  const name = custom.detail?.displayName || custom.detail?.userId;
  if (!name) {
    return;
  }

  if (composer.value.trim()) {
    composer.value = `${composer.value} @${name} `;
  } else {
    composer.value = `@${name} `;
  }

  nextTick(() => {
    composerRef.value?.focus?.();
  });
}

watch(
  () => props.workflowId,
  (workflowId) => {
    if (!workflowId) {
      comments.value = [];
      return;
    }
    knownCommentIds.value = new Set();
    void refreshComments();
    workflowRealtimeService.setWorkflowSubscription(workflowId);
  },
  { immediate: true }
);

watch(
  () => settings.frequency,
  () => {
    syncPolling();
  }
);

watch(
  () => settingsEnabled.value,
  () => {
    syncPolling();
  }
);

onMounted(() => {
  loadSettings();
  loadCommentCache();
  attachRealtime();
  syncPolling();
  window.addEventListener('workflow-mention-user', handleMentionShortcut as EventListener);
});

onBeforeUnmount(() => {
  if (pollTimer.value !== null) {
    window.clearInterval(pollTimer.value);
    pollTimer.value = null;
  }

  if (unsubRealtime.value) {
    unsubRealtime.value();
    unsubRealtime.value = null;
  }

  window.removeEventListener('workflow-mention-user', handleMentionShortcut as EventListener);
});

const CommentItem: any = defineComponent({
  name: 'CommentItem',
  props: {
    item: {
      type: Object as () => CommentTreeItem,
      required: true
    },
    batchMode: {
      type: Boolean,
      required: true
    },
    selectedIds: {
      type: Array as () => string[],
      required: true
    },
    currentUserId: {
      type: String,
      required: true
    },
    isAdmin: {
      type: Boolean,
      required: true
    },
    collapsedMap: {
      type: Object as () => Record<string, boolean>,
      required: true
    }
  },
  emits: ['reply', 'edit', 'delete', 'save-edit', 'cancel-edit', 'toggle-collapse', 'toggle-select', 'jump-mention'],
  setup(childProps, { emit }) {
    const canEditSelf = computed(() => !childProps.item.deleted && childProps.item.author_id === childProps.currentUserId);
    const canDeleteSelf = computed(
      () => !childProps.item.deleted && (childProps.item.author_id === childProps.currentUserId || childProps.isAdmin)
    );

    const visibleChildren = computed(() => {
      const collapsed = childProps.collapsedMap[childProps.item.comment_id];
      if (!collapsed) {
        return childProps.item.children;
      }
      return childProps.item.children.slice(0, 1);
    });

    return (): any =>
      h('article', { class: ['comment-item', `depth-${childProps.item.display_depth}`], 'data-comment-id': childProps.item.comment_id }, [
        h('div', { class: 'timeline-dot' }),
        h('div', { class: 'comment-bubble' }, [
          h('div', { class: 'item-header' }, [
            h('div', { class: 'author-line' }, [
              h('strong', childProps.item.author_name),
              childProps.item.reply_to_name ? h('span', { class: 'muted' }, `回复 ${childProps.item.reply_to_name}`) : null,
              h('span', { class: 'muted' }, new Date(childProps.item.created_at).toLocaleString())
            ]),
            childProps.batchMode && canDeleteSelf.value
              ? h('input', {
                  type: 'checkbox',
                  checked: childProps.selectedIds.includes(childProps.item.comment_id),
                  onChange: () => emit('toggle-select', childProps.item.comment_id)
                })
              : null
          ]),

          childProps.item.editing
            ? h('div', { class: 'edit-block' }, [
                h('textarea', {
                  class: 'edit-textarea',
                  value: childProps.item.edit_content,
                  onInput: (event: Event) => {
                    const target = event.target as HTMLTextAreaElement;
                    childProps.item.edit_content = target.value;
                  }
                }),
                h('div', { class: 'item-actions' }, [
                  h(
                    'button',
                    {
                      class: 'mini-btn primary',
                      onClick: () => emit('save-edit', childProps.item)
                    },
                    t('save')
                  ),
                  h(
                    'button',
                    {
                      class: 'mini-btn',
                      onClick: () => emit('cancel-edit', childProps.item)
                    },
                    t('cancel')
                  )
                ])
              ])
            : h('div', { class: 'item-content', innerHTML: renderHighlighted(childProps.item.content) }),

          h('div', { class: 'item-actions' }, [
            h(
              'button',
              {
                class: 'mini-btn',
                disabled: childProps.item.deleted,
                onClick: () => emit('reply', childProps.item)
              },
              t('answer')
            ),
            canEditSelf.value
              ? h(
                  'button',
                  {
                    class: 'mini-btn',
                    onClick: () => emit('edit', childProps.item)
                  },
                  t('edit')
                )
              : null,
            canDeleteSelf.value
              ? h(
                  'button',
                  {
                    class: 'mini-btn danger',
                    onClick: () => emit('delete', childProps.item)
                  },
                  t('delete')
                )
              : null,
            ...resolveMentions(childProps.item.content, childProps.item.mention_users).map((m) =>
              h(
                'button',
                {
                  class: 'mention-jump',
                  onClick: () => emit('jump-mention', m.display_name)
                },
                `@${m.display_name}`
              )
            )
          ]),

          childProps.item.children.length > 1
            ? h(
                'button',
                {
                  class: 'collapse-btn',
                  onClick: () => emit('toggle-collapse', childProps.item.comment_id)
                },
                childProps.collapsedMap[childProps.item.comment_id]
                  ? `${t('spreadout')} ${childProps.item.children.length - 1} ${t('piecereply')}`
                  : t('closereply')
              )
            : null,

          ...visibleChildren.value.map((child) =>
            h(CommentItem, {
              key: child.comment_id,
              item: child,
              batchMode: childProps.batchMode,
              selectedIds: childProps.selectedIds,
              currentUserId: childProps.currentUserId,
              isAdmin: childProps.isAdmin,
              collapsedMap: childProps.collapsedMap,
              onReply: (item: CommentTreeItem) => emit('reply', item),
              onEdit: (item: CommentTreeItem) => emit('edit', item),
              onDelete: (item: CommentTreeItem) => emit('delete', item),
              onSaveEdit: (item: CommentTreeItem) => emit('save-edit', item),
              onCancelEdit: (item: CommentTreeItem) => emit('cancel-edit', item),
              onToggleCollapse: (commentId: string) => emit('toggle-collapse', commentId),
              onToggleSelect: (commentId: string) => emit('toggle-select', commentId),
              onJumpMention: (displayName: string) => emit('jump-mention', displayName)
            })
          )
        ])
      ]);
  }
});
</script>

<style scoped>
.comment-thread {
  border: 1px solid #d9e2ef;
  border-radius: 12px;
  background: #fff;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 72vh;
  overflow: hidden;
}

.comment-header {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: center;
}

.header-main,
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-main h3 {
  margin: 0;
  font-size: 16px;
}

.settings-panel {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  border: 1px dashed #c7d7ea;
  border-radius: 10px;
  padding: 10px;
  background: #f8fbff;
}

.composer-card {
  border: 1px solid #e6eef9;
  border-radius: 10px;
  padding: 10px;
  position: relative;
}

.replying-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: #3c4b65;
  margin-bottom: 6px;
}

.mention-panel {
  position: absolute;
  z-index: 3;
  left: 10px;
  right: 10px;
  top: 110px;
  max-height: 200px;
  overflow: auto;
  border: 1px solid #d6e3f2;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.12);
}

.mention-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  cursor: pointer;
}

.mention-item.active,
.mention-item:hover {
  background: #ecf4ff;
}

.name-line {
  display: flex;
  align-items: center;
  gap: 8px;
}

.composer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}

.preview-box {
  margin-top: 8px;
  border: 1px solid #e6eef9;
  border-radius: 8px;
  padding: 8px;
  font-size: 13px;
  background: #f8fbff;
}

.list-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.comment-list {
  overflow: auto;
  padding-right: 4px;
}

.comment-item {
  position: relative;
  margin-left: 0;
  padding-left: 18px;
}

.comment-item.depth-1 {
  margin-left: 18px;
}

.comment-item.depth-2 {
  margin-left: 34px;
}

.timeline-dot {
  position: absolute;
  left: 2px;
  top: 16px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.18);
}

.comment-bubble {
  border-left: 2px solid #dde7f4;
  margin: 6px 0;
  padding: 8px 10px;
  border-radius: 8px;
  background: #fbfdff;
}

.item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 6px;
}

.author-line {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.item-content {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.5;
  white-space: normal;
  word-break: break-word;
}

.item-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.mini-btn,
.mention-jump,
.collapse-btn {
  border: 1px solid #d6e3f2;
  background: #fff;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1;
  padding: 5px 8px;
  cursor: pointer;
}

.mini-btn.primary {
  border-color: #3b82f6;
  color: #3b82f6;
}

.mini-btn.danger {
  border-color: #ef4444;
  color: #ef4444;
}

.mention-jump {
  border-color: #f59e0b;
  color: #b45309;
  background: #fff7ed;
}

.edit-block {
  margin-top: 6px;
}

.edit-textarea {
  width: 100%;
  min-height: 70px;
  border: 1px solid #d6e3f2;
  border-radius: 6px;
  padding: 8px;
  resize: vertical;
}

.load-more {
  display: flex;
  justify-content: center;
  padding: 10px 0 2px;
}

.jump-highlight {
  animation: comment-jump-highlight 1.4s ease;
}

.muted {
  color: #6b7280;
  font-size: 12px;
}

:deep(.mention) {
  color: #b45309;
  background: #fff7ed;
  border-radius: 4px;
  padding: 0 3px;
  font-weight: 600;
}

@keyframes comment-jump-highlight {
  0% {
    box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.4);
  }

  100% {
    box-shadow: 0 0 0 12px rgba(59, 130, 246, 0);
  }
}

@media (max-width: 960px) {
  .comment-thread {
    max-height: none;
  }

  .settings-panel {
    grid-template-columns: 1fr 1fr;
  }

  .list-toolbar {
    flex-wrap: wrap;
  }

  .comment-item.depth-1 {
    margin-left: 12px;
  }

  .comment-item.depth-2 {
    margin-left: 18px;
  }
}
</style>
