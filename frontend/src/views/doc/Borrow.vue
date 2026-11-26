<template>
  <div class="page">
    <div class="page__head">
      <h1 class="page__title">借用管理</h1>
      <span class="page__sub">提交即锁定资产「借用中」· 审批通过过户借用人 · 归还自动回原仓库</span>
    </div>

    <div class="card table-card">
      <div class="filter-bar">
        <el-input v-model="q.keyword" placeholder="借用单号" clearable :prefix-icon="Search" @keyup.enter="load" />
        <el-select v-model="q.status" placeholder="单据状态" clearable @change="page = 1, load()">
          <el-option v-for="(s, k) in DOC_STATUS" :key="k" :label="s.label" :value="Number(k)" />
        </el-select>
        <el-button type="primary" plain @click="load">查询</el-button>
        <el-button @click="reset">重置</el-button>
        <el-button v-perm="'borrow:create'" type="primary" :icon="Plus" style="margin-left: auto" @click="openCreate">新建借用单</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" height="100%">
        <el-table-column prop="borrow_no" label="借用单号" width="150" fixed />
        <el-table-column label="借用人" width="110">
          <template #default="{ row }">{{ userName(row.borrow_user) }}</template>
        </el-table-column>
        <el-table-column prop="borrow_date" label="借用日期" width="102" />
        <el-table-column prop="expected_return_date" label="预计归还" width="102" />
        <el-table-column label="状态" width="88" align="center">
          <template #default="{ row }">
            <el-tag :type="DOC_STATUS[row.status]?.type" size="small">{{ DOC_STATUS[row.status]?.label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="create_time" label="创建时间" width="150" :formatter="(_, __, v) => fmtDateTime(v)" />
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDetail(row)">明细</el-button>
            <el-button v-if="row.status === 0" link type="success" size="small" @click="submit(row)">{{ flowEnabled ? "提交审批" : "提交" }}</el-button>
            <el-button v-if="row.status === 1 && !flowEnabled" v-perm="'approval:approve'" link type="success" size="small" @click="manualApprove(row)">手动审批</el-button>
            <el-button v-if="row.status === 2" v-perm="'borrow:return'" link type="warning" size="small" @click="openReturn(row)">归还</el-button>
            <el-button v-if="row.status === 0 || row.status === 1" link type="danger" size="small" @click="cancel(row)">撤销</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <span class="text-muted">共 {{ total }} 张借用单</span>
        <el-pagination
          v-model:current-page="page" v-model:page-size="pageSize" :total="total"
          :page-sizes="[20, 50]" layout="sizes, prev, pager, next" background
          @current-change="load" @size-change="() => { page = 1; load(); }"
        />
      </div>
    </div>

    <!-- 明细抽屉 -->
    <el-drawer v-model="detailVisible" size="620px" :title="`借用单 ${detail.borrow_no || ''}`">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="借用人">{{ detail.borrow_user_name || userName(detail.borrow_user) || "-" }}</el-descriptions-item>
        <el-descriptions-item label="申请人">{{ detail.apply_user_name || userName(detail.apply_user) || "-" }}</el-descriptions-item>
        <el-descriptions-item label="借用日期">{{ fmtDate(detail.borrow_date) }}</el-descriptions-item>
        <el-descriptions-item label="预计归还">{{ fmtDate(detail.expected_return_date) }}</el-descriptions-item>
        <el-descriptions-item label="已还/总数">{{ detail.returned_num ?? 0 }} / {{ (detail.items || []).length }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="DOC_STATUS[detail.status]?.type" size="small">{{ DOC_STATUS[detail.status]?.label }}</el-tag>
        </el-descriptions-item>
      </el-descriptions>
      <div class="sec-title mt-12">借用明细</div>
      <el-table :data="detailItems" size="small" border>
        <el-table-column prop="asset_code" label="资产编码" width="150" />
        <el-table-column prop="asset_name" label="资产名称" min-width="120" show-overflow-tooltip />
        <el-table-column label="借出仓库" width="110">
          <template #default="{ row }">{{ row.src_warehouse_name || "-" }}</template>
        </el-table-column>
        <el-table-column label="归还状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.return_status === 1 ? 'success' : 'info'" size="small">
              {{ row.return_status === 1 ? '已归还' : '未归还' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="归还日期" width="102">
          <template #default="{ row }">{{ fmtDate(row.return_date) }}</template>
        </el-table-column>
        <el-table-column label="归还备注" min-width="90" show-overflow-tooltip>
          <template #default="{ row }">{{ row.return_note || "-" }}</template>
        </el-table-column>
      </el-table>
      <div class="sec-title mt-12">审批流程</div>
      <ApprovalFlowPanel :instance-id="detail.wf_instance_id" />
    </el-drawer>

    <!-- 新建 -->
    <el-dialog v-model="formVisible" title="新建借用单" width="780px" destroy-on-close top="5vh">
      <el-form :model="form" label-width="100px">
        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="借用单号">
              <el-input v-model="form.borrow_no" readonly placeholder="保存时自动生成">
                <template #append>
                  <el-button @click="refreshNo" :disabled="!formVisible">刷新</el-button>
                </template>
              </el-input>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="借用日期">
              <el-date-picker v-model="form.borrow_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="借用人" required>
              <el-select v-model="form.borrow_user" filterable placeholder="请选择借用人" style="width: 100%">
                <el-option v-for="u in users" :key="u.id" :label="u.real_name" :value="u.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="预计归还">
              <el-date-picker v-model="form.expected_return_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <div class="sec-title mt-12">
          选择资产
          <span class="text-muted asset-hint">限在库资产</span>
        </div>
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px">
          <el-button type="primary" plain @click="openAssetSelect">选择资产</el-button>
          <span class="text-muted">已选 <b>{{ selectedAssets.length }}</b> 项</span>
        </div>
        <el-table v-if="selectedAssets.length" :data="selectedAssets" size="small" border class="mt-8">
          <el-table-column prop="asset_code" label="资产编码" width="150" />
          <el-table-column prop="asset_name" label="名称" min-width="130" show-overflow-tooltip />
          <el-table-column prop="category_name" label="分类" width="90" show-overflow-tooltip />
          <el-table-column label="状态" width="80" align="center">
            <template #default="{ row }"><el-tag size="small">{{ assetStatusName(row.status) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="原值" width="90" align="right">
            <template #default="{ row }"><span class="num">{{ fmtMoney(row.price) }}</span></template>
          </el-table-column>
          <el-table-column label="使用位置" min-width="130">
            <template #default="{ row }">
              <el-input v-model="row.use_location" placeholder="借用后使用位置" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="64" align="center">
            <template #default="{ $index }">
              <el-button link type="danger" size="small" @click="selectedAssets.splice($index, 1)">移除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-form-item label="备注" class="mt-12">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button :loading="saving" @click="save(false)">保存草稿</el-button>
        <el-button type="primary" :loading="saving" @click="save(true)">发起审批</el-button>
      </template>
    </el-dialog>

    <!-- 归还 -->
    <el-dialog v-model="returnVisible" title="资产归还" width="640px" destroy-on-close>
      <div v-if="returnDoc" class="return-head">
        借用单 <b>{{ returnDoc.borrow_no }}</b> · 已还 {{ returnDoc.returned_num ?? 0 }}/{{ (returnDoc.items || []).length }}
      </div>
      <el-table
        v-if="returnItems.length"
        ref="returnTableRef"
        :data="returnItems" size="small" border
        @selection-change="onReturnSelection"
      >
        <el-table-column type="selection" width="40" :selectable="(row) => row.return_status !== 1" />
        <el-table-column prop="asset_code" label="资产编码" width="150" />
        <el-table-column prop="asset_name" label="资产名称" min-width="130" />
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.return_status === 1 ? 'success' : 'info'" size="small">
              {{ row.return_status === 1 ? '已归还' : '未归还' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      <div v-else class="text-muted">该借用单资产已全部归还</div>
      <el-form-item label="归还备注" class="mt-12">
        <el-input v-model="returnNote" type="textarea" :rows="2" placeholder="选填" />
      </el-form-item>
      <template #footer>
        <el-button @click="returnVisible = false">取消</el-button>
        <el-button type="primary" :loading="returning" :disabled="!returnSelected.length" @click="doReturn">
          确认归还（{{ returnSelected.length }}）
        </el-button>
      </template>
    </el-dialog>

    <!-- 资产选择弹窗 -->
    <AssetSelectDialog
      v-model="assetSelectVisible"
      title="选择在库资产"
      :allow-statuses="[1]"
      :preset="assetSelectPreset"
      @confirm="onAssetConfirmed"
    />
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Search, Plus } from "@element-plus/icons-vue";
import { docApi, assetApi, sysApi } from "../../api";
import AssetSelectDialog from "../../components/AssetSelectDialog.vue";
import ApprovalFlowPanel from "../../components/ApprovalFlowPanel.vue";
import { DOC_STATUS, fmtDate, fmtDateTime, todayStr, assetStatusName, fmtMoney } from "../../utils/constants";
import { loadFlowEnabled } from "../../utils/approval";

const flowEnabled = ref(true);
const loading = ref(false);
const saving = ref(false);
const submitting = ref(false);
const rows = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const q = reactive({ keyword: "", status: null });
const users = ref([]);

const userName = (id) => (id ? users.value.find((u) => u.id === id)?.real_name : "") || "-";

async function load() {
  loading.value = true;
  try {
    const params = { page: page.value, page_size: pageSize.value };
    if (q.keyword) params.keyword = q.keyword;
    if (q.status !== null) params.status = q.status;
    const res = await docApi.borrows(params);
    rows.value = res.records;
    total.value = res.total;
  } finally {
    loading.value = false;
  }
}
function reset() {
  q.keyword = "";
  q.status = null;
  page.value = 1;
  load();
}

// ---- 明细 ----
const detailVisible = ref(false);
const detail = ref({});
const detailItems = ref([]);
async function openDetail(row) {
  detail.value = await docApi.borrow(row.id);
  const items = detail.value.items || [];
  detailItems.value = await Promise.all(
    items.map(async (i) => {
      try {
        const a = await assetApi.detail(i.asset_id);
        return { ...i, asset_code: a.asset_code, asset_name: a.asset_name };
      } catch {
        return { ...i, asset_code: `#${i.asset_id}`, asset_name: "-" };
      }
    })
  );
  detailVisible.value = true;
}

// ---- 新建 ----
const formVisible = ref(false);
const form = reactive({
  borrow_no: "",
  borrow_user: null,
  borrow_date: "",
  expected_return_date: "",
  remark: "",
});
const selectedAssets = ref([]);

async function refreshNo() {
  try {
    const res = await docApi.nextDocNo("borrow");
    form.borrow_no = res.next_no;
  } catch {
    form.borrow_no = "";
  }
}

// ---- 资产选择弹窗 ----
const assetSelectVisible = ref(false);
const assetSelectPreset = ref([]);
function openAssetSelect() {
  assetSelectPreset.value = selectedAssets.value;
  assetSelectVisible.value = true;
}
function onAssetConfirmed(assets) {
  const existing = new Set(selectedAssets.value.map((a) => a.id));
  const newOnes = assets.filter((a) => !existing.has(a.id));
  if (newOnes.length) selectedAssets.value = [...selectedAssets.value, ...newOnes];
}

function openCreate() {
  Object.assign(form, {
    borrow_no: "",
    borrow_user: null,
    borrow_date: todayStr(),
    expected_return_date: "",
    remark: "",
  });
  selectedAssets.value = [];
  formVisible.value = true;
  refreshNo();
}
function save(submit = false) {
  if (!form.borrow_user) return ElMessage.warning("请选择借用人");
  if (!selectedAssets.value.length) return ElMessage.warning("请选择借用资产");
  saving.value = true;
  (async () => {
    try {
      const created = await docApi.createBorrow({
        borrow_user: form.borrow_user,
        borrow_date: form.borrow_date || null,
        expected_return_date: form.expected_return_date || null,
        remark: form.remark || null,
        items: selectedAssets.value.map((a) => ({
          asset_id: a.id,
          use_location: a.use_location || null,
        })),
      });
      if (submit) {
        const res = await docApi.submit("borrow", created.id);
        ElMessage.success(res.manual ? "已提交，待手动审批通过" : "已提交审批，资产已锁定为「借用中」");
      } else {
        ElMessage.success("借用单已保存（草稿），编号自动生成");
      }
      formVisible.value = false;
      load();
    } finally {
      saving.value = false;
    }
  })();
}

async function submit(row) {
  if (submitting.value) return;
  try {
    const tip = flowEnabled.value
      ? `提交后单据进入审批流并锁定资产，确认提交「${row.borrow_no || row.id}」？`
      : `提交后单据待手动审批，确认提交「${row.borrow_no || row.id}」？`;
    await ElMessageBox.confirm(tip, flowEnabled.value ? "提交审批" : "提交", { type: "warning" });
  } catch {
    return;
  }
  submitting.value = true;
  try {
    const res = await docApi.submit("borrow", row.id);
    ElMessage.success(res.manual ? "已提交，待手动审批通过" : "已提交审批，资产已锁定为「借用中」");
    load();
  } finally {
    submitting.value = false;
  }
}
async function manualApprove(row) {
  try {
    await ElMessageBox.confirm("手动审批通过后单据立即生效，确认通过？", "手动审批", { type: "warning" });
  } catch {
    return;
  }
  await docApi.manualApprove("borrow", row.id);
  ElMessage.success("已手动审批通过，单据已生效");
  load();
}
async function cancel(row) {
  try {
    await ElMessageBox.confirm("撤销后单据作废，资产恢复原状态，确认撤销？", "撤销", { type: "warning" });
  } catch {
    return;
  }
  await docApi.cancel("borrow", row.id);
  ElMessage.success("已撤销");
  load();
}

// ---- 归还 ----
const returnVisible = ref(false);
const returnDoc = ref(null);
const returnItems = ref([]);
const returnSelected = ref([]);
const returnNote = ref("");
const returning = ref(false);
const returnTableRef = ref(null);
async function openReturn(row) {
  const d = await docApi.borrow(row.id);
  returnDoc.value = d;
  const items = d.items || [];
  returnItems.value = await Promise.all(
    items.map(async (i) => {
      try {
        const a = await assetApi.detail(i.asset_id);
        return { ...i, asset_code: a.asset_code, asset_name: a.asset_name };
      } catch {
        return { ...i, asset_code: `#${i.asset_id}`, asset_name: "-" };
      }
    })
  );
  returnSelected.value = [];
  returnNote.value = "";
  returnVisible.value = true;
}
function onReturnSelection(sel) {
  returnSelected.value = sel;
}
async function doReturn() {
  if (!returnSelected.value.length) return;
  returning.value = true;
  try {
    await docApi.returnBorrow(returnDoc.value.id, {
      asset_ids: returnSelected.value.map((x) => x.asset_id),
      note: returnNote.value || null,
    });
    ElMessage.success("归还成功，资产已回库");
    returnVisible.value = false;
    load();
  } finally {
    returning.value = false;
  }
}

onMounted(async () => {
  flowEnabled.value = await loadFlowEnabled("borrow");
  try {
    const us = await sysApi.users({ page: 1, page_size: 200 });
    users.value = (us.records || []).filter((u) => u.status === 1);
  } catch {
    users.value = [];
  }
  load();
});
</script>

<style scoped>
.table-card { flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
.asset-hint { font-size: 12px; font-weight: 400; margin-left: 8px; }
.return-head { font-size: 13px; margin-bottom: 12px; }
</style>