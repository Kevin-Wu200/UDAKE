<template>
  <div class="ticket-management">
    <div class="filter-area">
      <el-select v-model="filters.status" :placeholder="tc('status')" clearable style="width: 150px">
        <el-option :label="tc('pending')" value="pending" />
        <el-option :label="tc('approved')" value="approved" />
        <el-option :label="tc('rejected')" value="rejected" />
        <el-option :label="tc('completed')" value="completed" />
      </el-select>
      <el-select v-model="filters.ticket_type" :placeholder="tc('type')" clearable style="width: 150px">
        <el-option :label="tc('keyRequest')" value="key_request" />
        <el-option :label="tc('keyExtension')" value="key_extension" />
      </el-select>
      <el-input v-model="filters.search" :placeholder="tc('searchEmail')" style="width: 200px" />
      <el-button type="primary" @click="loadData">{{ tc('query') }}</el-button>
    </div>

    <el-table v-loading="ticketStore.loading" :data="ticketStore.tickets" border style="width: 100%">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="type" :label="tc('type')">
        <template #default="{ row }">{{ row.type === 'key_request' ? tc('keyRequest') : tc('keyExtension') }}</template>
      </el-table-column>
      <el-table-column prop="applicant_email" :label="tc('applicant')" />
      <el-table-column prop="status" :label="tc('status')">
        <template #default="{ row }"><StatusTag :status="row.status" /></template>
      </el-table-column>
      <el-table-column prop="created_at" :label="tc('createAt')" />
      <el-table-column :label="tc('action')" width="200">
        <template #default="{ row }">
          <el-button link @click="viewDetail(row.id)">{{ tc('check') }}</el-button>
          <el-button v-if="row.status === 'pending'" link type="primary" @click="openApprove(row)">{{tc('approve')}}</el-button>
          <el-button v-if="row.status === 'pending'" link type="danger" @click="openReject(row)">{{tc('reject')}}</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="pagination.page"
      v-model:page-size="pagination.page_size"
      :total="ticketStore.total"
      layout="total, prev, pager, next"
      @current-change="loadData"
    />

    <ApprovalDialog ref="approveDialog" type="approve" @confirm="onApprove" />
    <ApprovalDialog ref="rejectDialog" type="reject" @confirm="onReject" />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useTicketStore } from '../stores/ticket';
import StatusTag from '../components/StatusTag.vue';
import ApprovalDialog from '../components/ApprovalDialog.vue';
import { ElMessage } from 'element-plus';
import type { Ticket, TicketListParams } from '../types/ticket';
import { useI18nText } from '../i18n/useI18n';

const { tc } = useI18nText();
const router = useRouter();
const ticketStore = useTicketStore();
const filters = reactive<{
  status?: TicketListParams['status'];
  ticket_type?: TicketListParams['ticket_type'];
  search: string;
}>({ status: undefined, ticket_type: undefined, search: '' });
const pagination = reactive({ page: 1, page_size: 10 });
const approveDialog = ref();
const rejectDialog = ref();
const currentActionTicket = ref<Ticket | null>(null);

const loadData = () => {
  ticketStore.fetchTickets({ ...pagination, ...filters });
};

const viewDetail = (id: number) => router.push(`/admin/tickets/${id}`);

const openApprove = (row: Ticket) => {
  currentActionTicket.value = row;
  approveDialog.value.open();
};

const openReject = (row: Ticket) => {
  currentActionTicket.value = row;
  rejectDialog.value.open();
};

const onApprove = async (notes: string) => {
  if (!currentActionTicket.value) {
    return;
  }
  await ticketStore.approve(currentActionTicket.value.id, notes);
  ElMessage.success(tc('approveSuccess'));
  approveDialog.value.close();
  loadData();
};

const onReject = async (reason: string) => {
  if (!currentActionTicket.value) {
    return;
  }
  await ticketStore.reject(currentActionTicket.value.id, reason);
  ElMessage.success(tc('rejectSuccess'));
  rejectDialog.value.close();
  loadData();
};

onMounted(loadData);
</script>
