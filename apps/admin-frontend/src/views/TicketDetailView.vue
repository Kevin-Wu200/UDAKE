<template>
  <div v-if="ticketStore.currentTicket" class="ticket-detail">
    <el-card>
      <template #header>
        <div class="header">
          <span>工单详情 #{{ ticketStore.currentTicket.id }}</span>
          <el-button @click="$router.back()">返回</el-button>
        </div>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="状态"><StatusTag :status="ticketStore.currentTicket.status" /></el-descriptions-item>
        <el-descriptions-item label="类型">{{ ticketStore.currentTicket.type === 'key_request' ? '申请' : '延期' }}</el-descriptions-item>
        <el-descriptions-item label="申请人">{{ ticketStore.currentTicket.applicant_email }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ ticketStore.currentTicket.created_at }}</el-descriptions-item>
      </el-descriptions>
      <div v-if="ticketStore.currentTicket.status === 'pending'" class="actions">
        <el-button type="primary" @click="openApprove">批准</el-button>
        <el-button type="danger" @click="openReject">拒绝</el-button>
      </div>
    </el-card>
    <ApprovalDialog ref="approveDialog" type="approve" @confirm="onApprove" />
    <ApprovalDialog ref="rejectDialog" type="reject" @confirm="onReject" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import { useTicketStore } from '../stores/ticket';
import StatusTag from '../components/StatusTag.vue';
import ApprovalDialog from '../components/ApprovalDialog.vue';
import { ElMessage } from 'element-plus';

const route = useRoute();
const ticketStore = useTicketStore();
const approveDialog = ref();
const rejectDialog = ref();

const load = () => ticketStore.fetchTicketDetail(Number(route.params.id));

const openApprove = () => approveDialog.value.open();
const openReject = () => rejectDialog.value.open();

const onApprove = async (notes: string) => {
  await ticketStore.approve(ticketStore.currentTicket!.id, notes);
  ElMessage.success('批准成功');
  approveDialog.value.close();
  load();
};

const onReject = async (reason: string) => {
  await ticketStore.reject(ticketStore.currentTicket!.id, reason);
  ElMessage.success('拒绝成功');
  rejectDialog.value.close();
  load();
};

onMounted(load);
</script>
