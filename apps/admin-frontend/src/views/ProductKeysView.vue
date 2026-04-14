<template>
  <div class="page-card">
    <div class="toolbar">
      <el-select v-model="filters.type" clearable placeholder="类型" style="width: 140px">
        <el-option label="试用" value="trial" />
        <el-option label="标准" value="standard" />
        <el-option label="企业" value="enterprise" />
      </el-select>

      <el-select v-model="filters.status" clearable placeholder="状态" style="width: 140px">
        <el-option label="未使用" value="unused" />
        <el-option label="已激活" value="active" />
        <el-option label="已禁用" value="disabled" />
      </el-select>

      <el-input v-model="filters.keyword" placeholder="搜索密钥/企业" style="width: 240px" clearable />
      <el-button type="primary" @click="search">查询</el-button>
      <el-button @click="resetSearch">重置</el-button>
      <el-button type="success" @click="createDialogVisible = true">创建密钥</el-button>
      <el-button type="warning" @click="importDialogVisible = true">批量导入</el-button>
    </div>

    <el-table :data="list" border>
      <el-table-column prop="key" label="密钥" min-width="200" />
      <el-table-column prop="type" label="类型" width="110">
        <template #default="scope">{{ typeText(scope.row.type) }}</template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="110">
        <template #default="scope">
          <el-tag :type="statusTag(scope.row.status)">{{ statusText(scope.row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="usageCount" label="使用次数" width="100" />
      <el-table-column prop="enterpriseName" label="企业名称" min-width="150" />
      <el-table-column prop="createdAt" label="创建时间" width="170" />
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="scope">
          <el-button size="small" @click="openEdit(scope.row)">编辑</el-button>
          <el-button size="small" type="danger" @click="onDelete(scope.row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination">
      <el-pagination
        background
        layout="total, prev, pager, next, sizes"
        :current-page="page"
        :page-size="pageSize"
        :page-sizes="[10, 20, 50]"
        :total="total"
        @current-change="onPageChange"
        @size-change="onPageSizeChange"
      />
    </div>
  </div>

  <el-dialog v-model="createDialogVisible" title="批量创建密钥" width="420px">
    <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="90px">
      <el-form-item label="类型" prop="type">
        <el-select v-model="createForm.type" style="width: 100%">
          <el-option label="试用" value="trial" />
          <el-option label="标准" value="standard" />
          <el-option label="企业" value="enterprise" />
        </el-select>
      </el-form-item>
      <el-form-item label="数量" prop="quantity">
        <el-input-number v-model="createForm.quantity" :min="1" :max="500" style="width: 100%" />
      </el-form-item>
      <el-form-item label="企业名称" prop="enterpriseName">
        <el-input v-model="createForm.enterpriseName" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="createDialogVisible = false">取消</el-button>
      <el-button type="primary" @click="onCreate">批量生成</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="importDialogVisible" title="批量导入密钥" width="520px">
    <el-alert
      type="info"
      :closable="false"
      title="每行格式：key,type,status,enterpriseName。type取值 trial/standard/enterprise；status取值 unused/active/disabled"
    />
    <el-input
      v-model="importText"
      type="textarea"
      :rows="9"
      style="margin-top: 12px"
      placeholder="示例: UDAKE-ABCD-EFGH-IJKL,standard,unused,企业A"
    />
    <div v-if="importResult" class="import-result">
      <el-tag type="success">成功 {{ importResult.successCount }}</el-tag>
      <el-tag type="danger">失败 {{ importResult.failedCount }}</el-tag>
      <el-text v-if="importResult.failedLines.length" type="danger">
        失败行：{{ importResult.failedLines.join(' | ') }}
      </el-text>
    </div>
    <template #footer>
      <el-button @click="importDialogVisible = false">取消</el-button>
      <el-button type="primary" @click="onImport">解析并导入</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="editDialogVisible" title="编辑密钥" width="420px">
    <el-form ref="editFormRef" :model="editForm" :rules="editRules" label-width="90px">
      <el-form-item label="状态" prop="status">
        <el-select v-model="editForm.status" style="width: 100%">
          <el-option label="未使用" value="unused" />
          <el-option label="已激活" value="active" />
          <el-option label="已禁用" value="disabled" />
        </el-select>
      </el-form-item>
      <el-form-item label="企业名称" prop="enterpriseName">
        <el-input v-model="editForm.enterpriseName" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="editDialogVisible = false">取消</el-button>
      <el-button type="primary" @click="onUpdate">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import type { FormInstance, FormRules } from 'element-plus';
import type { KeyStatus, KeyType, ProductKey } from '../types/admin';
import { onMounted, reactive, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import {
  createProductKeys,
  deleteProductKey,
  fetchProductKeys,
  importProductKeys,
  updateProductKey
} from '../services/mockApi';

const list = ref<ProductKey[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(10);

const filters = reactive<{
  type?: KeyType;
  status?: KeyStatus;
  keyword: string;
}>({
  type: undefined,
  status: undefined,
  keyword: ''
});

const createDialogVisible = ref(false);
const importDialogVisible = ref(false);
const editDialogVisible = ref(false);

const createFormRef = ref<FormInstance>();
const editFormRef = ref<FormInstance>();

const createForm = reactive({
  type: 'standard' as KeyType,
  quantity: 10,
  enterpriseName: ''
});

const editForm = reactive({
  id: 0,
  status: 'unused' as KeyStatus,
  enterpriseName: ''
});

const importText = ref('');
const importResult = ref<{
  successCount: number;
  failedCount: number;
  failedLines: string[];
} | null>(null);

const createRules: FormRules<typeof createForm> = {
  type: [{ required: true, message: '请选择类型', trigger: 'change' }],
  quantity: [{ required: true, message: '请输入数量', trigger: 'change' }],
  enterpriseName: [{ required: true, message: '请输入企业名称', trigger: 'blur' }]
};

const editRules: FormRules<typeof editForm> = {
  status: [{ required: true, message: '请选择状态', trigger: 'change' }],
  enterpriseName: [{ required: true, message: '请输入企业名称', trigger: 'blur' }]
};

const typeText = (type: KeyType) => {
  const map: Record<KeyType, string> = {
    trial: '试用',
    standard: '标准',
    enterprise: '企业'
  };
  return map[type];
};

const statusText = (status: KeyStatus) => {
  const map: Record<KeyStatus, string> = {
    unused: '未使用',
    active: '已激活',
    disabled: '已禁用'
  };
  return map[status];
};

const statusTag = (status: KeyStatus): 'success' | 'warning' | 'info' => {
  if (status === 'active') {
    return 'success';
  }
  if (status === 'disabled') {
    return 'warning';
  }
  return 'info';
};

const loadList = async () => {
  try {
    const res = await fetchProductKeys({
      page: page.value,
      pageSize: pageSize.value,
      type: filters.type,
      status: filters.status,
      keyword: filters.keyword
    });
    list.value = res.items;
    total.value = res.total;
  } catch {
    ElMessage.error('获取密钥列表失败');
  }
};

const search = () => {
  page.value = 1;
  loadList();
};

const resetSearch = () => {
  filters.type = undefined;
  filters.status = undefined;
  filters.keyword = '';
  page.value = 1;
  loadList();
};

const onPageChange = (nextPage: number) => {
  page.value = nextPage;
  loadList();
};

const onPageSizeChange = (size: number) => {
  pageSize.value = size;
  page.value = 1;
  loadList();
};

const onCreate = async () => {
  if (!createFormRef.value) {
    return;
  }

  try {
    await createFormRef.value.validate();
    await createProductKeys({
      type: createForm.type,
      quantity: createForm.quantity,
      enterpriseName: createForm.enterpriseName
    });
    createDialogVisible.value = false;
    createForm.enterpriseName = '';
    ElMessage.success('批量创建成功');
    loadList();
  } catch {
    ElMessage.error('批量创建失败');
  }
};

const onImport = async () => {
  if (!importText.value.trim()) {
    ElMessage.warning('请输入导入内容');
    return;
  }

  try {
    importResult.value = await importProductKeys(importText.value);
    ElMessage.success('导入已完成');
    loadList();
  } catch {
    ElMessage.error('导入失败');
  }
};

const openEdit = (row: ProductKey) => {
  editForm.id = row.id;
  editForm.status = row.status;
  editForm.enterpriseName = row.enterpriseName;
  editDialogVisible.value = true;
};

const onUpdate = async () => {
  if (!editFormRef.value) {
    return;
  }

  try {
    await editFormRef.value.validate();
    await updateProductKey(editForm.id, {
      status: editForm.status,
      enterpriseName: editForm.enterpriseName
    });
    editDialogVisible.value = false;
    ElMessage.success('更新成功');
    loadList();
  } catch {
    ElMessage.error('更新失败');
  }
};

const onDelete = async (row: ProductKey) => {
  try {
    await ElMessageBox.confirm(`确认删除密钥 ${row.key} 吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      modalClass: 'admin-confirm-dialog-overlay',
      closeOnClickModal: false,
      closeOnPressEscape: false
    });
    await deleteProductKey(row.id);
    ElMessage.success('删除成功');
    if (list.value.length === 1 && page.value > 1) {
      page.value -= 1;
    }
    loadList();
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      console.error('删除密钥失败:', error);
      ElMessage.error('操作失败，请重试');
    }
  }
};

onMounted(() => {
  loadList();
});
</script>

<style scoped>
.import-result {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
</style>
