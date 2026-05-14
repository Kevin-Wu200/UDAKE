<template>
  <div v-if="ticketStore.currentTicket" class="ticket-detail">
    <el-card>
      <template #header>
        <div class="header">
          <span>{{ tc('ticketDetail', {ticketId: ticketStore.currentTicket.ticket_id}) }}</span>
          <el-button @click="$router.back()" style="margin-left: 25px;">{{ tc('back') }}</el-button>
        </div>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item :label="tc('ticketId')">{{ ticketStore.currentTicket.ticket_id }}</el-descriptions-item>
        <el-descriptions-item :label="tc('status')"><StatusTag :status="ticketStore.currentTicket.status" /></el-descriptions-item>
        <el-descriptions-item :label="tc('type')">{{ ticketStore.currentTicket.ticket_type === 'key_request' ? tc('keyRequest') : tc('keyExtension') }}</el-descriptions-item>
        <el-descriptions-item :label="tc('email')">{{ ticketStore.currentTicket.email }}</el-descriptions-item>
        <el-descriptions-item :label="tc('phone')">{{ ticketStore.currentTicket.phone }}</el-descriptions-item>
        <el-descriptions-item :label="tc('industry')">{{ ticketStore.currentTicket.industry }}</el-descriptions-item>
        <el-descriptions-item :label="tc('organization')">{{ ticketStore.currentTicket.organization }}</el-descriptions-item>
        <el-descriptions-item :label="tc('usagePurpose')" :span="2">{{ ticketStore.currentTicket.usage_purpose }}</el-descriptions-item>
        <el-descriptions-item :label="tc('keyType')">{{ keyTypeDisplayName }}</el-descriptions-item>
        <el-descriptions-item :label="tc('existingKey')">{{ ticketStore.currentTicket.existing_key || '-' }}</el-descriptions-item>
        <el-descriptions-item :label="tc('assignedKey')">{{ ticketStore.currentTicket.assigned_key || '-' }}</el-descriptions-item>
        <el-descriptions-item :label="tc('responseMessage')" :span="2">{{ ticketStore.currentTicket.response_message || '-' }}</el-descriptions-item>
        <el-descriptions-item :label="tc('approvalNotes')" :span="2">{{ ticketStore.currentTicket.approval_notes || '-' }}</el-descriptions-item>
        <el-descriptions-item :label="tc('processedBy')">{{ ticketStore.currentTicket.processed_by ?? tc('notProcessed') }}</el-descriptions-item>
        <el-descriptions-item :label="tc('processedAt')">{{ formatTicketTime(ticketStore.currentTicket.processed_at) }}</el-descriptions-item>
        <el-descriptions-item :label="tc('createAt')">{{ formatTicketTime(ticketStore.currentTicket.created_at) }}</el-descriptions-item>
        <el-descriptions-item :label="tc('updatedAt')">{{ formatTicketTime(ticketStore.currentTicket.updated_at) }}</el-descriptions-item>
      </el-descriptions>
      <div v-if="ticketStore.currentTicket.status === 'pending'" class="actions">
        <el-button type="primary" @click="openApprove">{{ tc('approveTicket') }}</el-button>
        <el-button type="danger" @click="openReject">{{ tc('rejectTicket') }}</el-button>
      </div>
    </el-card>
    <ApprovalDialog ref="approveDialog" type="approve" @confirm="onApprove" />
    <ApprovalDialog ref="rejectDialog" type="reject" @confirm="onReject" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import { useTicketStore } from '../stores/ticket';
import StatusTag from '../components/StatusTag.vue';
import ApprovalDialog from '../components/ApprovalDialog.vue';
import { ElMessage } from 'element-plus';
import { useI18nText } from '../i18n/useI18n';
import { formatTicketTime } from '../utils/auth';

const route = useRoute();
const ticketStore = useTicketStore();
const { tc } = useI18nText();
const approveDialog = ref();
const rejectDialog = ref();

const keyTypeI18nMap: Record<string, string> = {
  personal_trial: 'personalTrial',
  personal_standard: 'personalStandard',
  enterprise_trial: 'enterpriseTrial',
  enterprise_standard: 'enterpriseStandard',
};

const keyTypeDisplayName = computed(() => {
  const kt = ticketStore.currentTicket?.key_type;
  const i18nKey = kt ? keyTypeI18nMap[kt] : undefined;
  return i18nKey ? tc(i18nKey) : (kt || '-');
});

const load = () => ticketStore.fetchTicketDetail(route.params.id as string);

const openApprove = () => approveDialog.value.open();
const openReject = () => rejectDialog.value.open();

const onApprove = async (notes: string) => {
  await ticketStore.approve(ticketStore.currentTicket!.ticket_id, notes);
  ElMessage.success(tc('approveSuccess'));
  approveDialog.value.close();
  load();
};

const onReject = async (reason: string) => {
  await ticketStore.reject(ticketStore.currentTicket!.ticket_id, reason);
  ElMessage.success(tc('rejectSuccess'));
  rejectDialog.value.close();
  load();
};

onMounted(load);
</script>
