<template>
  <div class="ticket-management">
    <div class="filter-area">
      <el-select v-model="filters.status" placeholder="状态" clearable style="width: 150px">
        <el-option label="待处理" value="pending" />
        <el-option label="已批准" value="approved" />
        <el-option label="已拒绝" value="rejected" />
        <el-option label="已完成" value="completed" />
      </el-select>
      <el-select v-model="filters.ticket_type" placeholder="类型" clearable style="width: 150px">
        <el-option label="密钥申请" value="key_request" />
        <el-option label="密钥延期" value="key_extension" />
      </el-select>
      <el-input v-model="filters.search" placeholder="搜索邮箱/ID" style="width: 200px" />
      <el-button type="primary" @click="loadData">查询</el-button>
    </div>

    <el-table v-loading="ticketStore.loading" :data="ticketStore.tickets" border style="width: 100%">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="type" label="类型">
        <template #default="{ row }">{{ row.type === 'key_request' ? '密钥申请' : '密钥延期' }}</template>
      </el-table-column>
      <el-table-column prop="applicant_email" label="申请者" />
      <el-table-column prop="status" label="状态">
        <template #default="{ row }"><StatusTag :status="row.status" /></template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" />
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button link @click="viewDetail(row.id)">查看</el-button>
          <el-button v-if="row.status === 'pending'" link type="primary" @click="openApprove(row)">批准</el-button>
          <el-button v-if="row.status === 'pending'" link type="danger" @click="openReject(row)">拒绝</el-button>
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
  ElMessage.success('批准成功');
  approveDialog.value.close();
  loadData();
};

const onReject = async (reason: string) => {
  if (!currentActionTicket.value) {
    return;
  }
  await ticketStore.reject(currentActionTicket.value.id, reason);
  ElMessage.success('拒绝成功');
  rejectDialog.value.close();
  loadData();
};

onMounted(loadData);
</script>
