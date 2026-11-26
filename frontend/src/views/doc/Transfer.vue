<template>
  <div class="page">
    <div class="page__head">
      <h1 class="page__title">调拨管理</h1>
      <span class="page__sub">提交即锁定资产「调拨中」· 审批通过自动过户并写履历</span>
    </div>

    <div class="card table-card">
      <div class="filter-bar">
        <el-input v-model="q.keyword" placeholder="调拨单号" clearable :prefix-icon="Search" @keyup.enter="load" />
        <el-select v-model="q.status" placeholder="单据状态" clearable @change="page = 1, load()">
          <el-option v-for="(s, k) in DOC_STATUS" :key="k" :label="s.label" :value="Number(k)" />
        </el-select>
        <el-button type="primary" plain @click="load">查询</el-button>
        <el-button @click="reset">重置</el-button>
        <el-button v-perm="'transfer:create'" type="primary" :icon="Plus" style="margin-left: auto" @click="openCreate">新建调拨单</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" height="100%">
        <el-table-column prop="transfer_no" label="调拨单号" width="150" fixed />
        <el-table-column label="调拨类型" width="120" align="center">
          <template #default="{ row }">{{ TRANSFER_TYPE[row.transfer_type] || "-" }}</template>
        </el-table-column>
        <el-table-column label="调出位置" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ outLoc(row) }}</template>
        </el-table-column>
        <el-table-column label="调入位置" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ inLoc(row) }}</template>
        </el-table-column>
        <el-table-column prop="transfer_date" label="调拨日期" width="102" />
        <el-table-column label="状态" width="88" align="center">
          <template #default="{ row }">
            <el-tag :type="DOC_STATUS[row.status]?.type" size="small">{{ DOC_STATUS[row.status]?.label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="create_time" label="创建时间" width="150" :formatter="(_, __, v) => fmtDateTime(v)" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDetail(row)">明细</el-button>
            <el-button v-if="row.status === 0" link type="success" size="small" @click="submit(row)">{{ flowEnabled ? "提交审批" : "提交" }}</el-button>
            <el-button v-if="row.status === 1 && !flowEnabled" v-perm="'approval:approve'" link type="success" size="small" @click="manualApprove(row)">手动审批</el-button>
            <el-button v-if="row.status === 0 || row.status === 1" link type="danger" size="small" @click="cancel(row)">撤销</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <span class="text-muted">共 {{ total }} 张调拨单</span>
        <el-pagination
          v-model:current-page="page" v-model:page-size="pageSize" :total="total"
          :page-sizes="[20, 50]" layout="sizes, prev, pager, next" background
          @current-change="load" @size-change="() => { page = 1; load(); }"
        />
      </div>
    </div>

    <!-- 明细抽屉 -->
    <el-drawer v-model="detailVisible" size="600px" :title="`调拨单 ${detail.transfer_no || ''}`">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="调拨类型">{{ TRANSFER_TYPE[detail.transfer_type] || "-" }}</el-descriptions-item>
        <el-descriptions-item label="调拨日期">{{ fmtDate(detail.transfer_date) }}</el-descriptions-item>
        <el-descriptions-item label="调出位置">{{ detailLoc(detail, "out") }}</el-descriptions-item>
        <el-descriptions-item label="调入位置">{{ detailLoc(detail, "in") }}</el-descriptions-item>
        <el-descriptions-item label="状态" :span="2">
          <el-tag :type="DOC_STATUS[detail.status]?.type" size="small">{{ DOC_STATUS[detail.status]?.label }}</el-tag>
        </el-descriptions-item>
      </el-descriptions>
      <div class="sec-title mt-12">调拨明细</div>
      <el-table :data="detailItems" size="small" border>
        <el-table-column prop="asset_code" label="资产编码" width="165" />
        <el-table-column prop="asset_name" label="资产名称" min-width="120" />
        <el-table-column label="数量" width="60" align="center">
          <template #default="{ row }">{{ row.num }}</template>
        </el-table-column>
        <el-table-column label="调入后位置" width="120">
          <template #default="{ row }">{{ row.use_location || "-" }}</template>
        </el-table-column>
        <el-table-column label="责任人" width="80">
          <template #default="{ row }">{{ row.use_user_name || "-" }}</template>
        </el-table-column>
        <el-table-column label="责任部门" width="100">
          <template #default="{ row }">{{ row.use_dept_name || "-" }}</template>
        </el-table-column>
      </el-table>
      <div class="sec-title mt-12">审批流程</div>
      <ApprovalFlowPanel :instance-id="detail.wf_instance_id" />
    </el-drawer>

    <!-- 新建 -->
    <el-dialog v-model="formVisible" title="新建调拨单" width="780px" destroy-on-close top="5vh">
      <el-form :model="form" label-width="100px">
        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="调拨单号">
              <el-input v-model="form.transfer_no" readonly placeholder="保存时自动生成">
                <template #append>
                  <el-button @click="refreshNo" :disabled="!formVisible">刷新</el-button>
                </template>
              </el-input>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="调拨日期">
              <el-date-picker v-model="form.transfer_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="调拨类型" required>
              <el-radio-group v-model="form.transfer_type" @change="onTransferTypeChange">
                <el-radio-button :value="1">仓库调拨</el-radio-button>
                <el-radio-button :value="2">项目空间调拨</el-radio-button>
                <el-radio-button :value="4">部门调拨</el-radio-button>
              </el-radio-group>
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 调出 / 调入 -->
        <div class="loc-grid">
          <div class="loc-box">
            <div class="loc-box__title">调出（来源）</div>
            <template v-if="form.transfer_type === 1">
              <div class="loc-box__label">调出仓库 <b class="req">*</b></div>
              <el-select v-model="form.out_warehouse_id" filterable placeholder="请选择调出仓库" style="width: 100%" @change="clearPicked">
                <el-option v-for="w in warehouses" :key="w.id" :label="w.warehouse_name" :value="w.id" />
              </el-select>
            </template>
            <template v-else-if="form.transfer_type === 2">
              <div class="loc-box__label">调出项目空间（末级） <b class="req">*</b></div>
              <el-tree-select
                v-model="form.out_project_id" :data="spaceTree" node-key="id"
                :props="{ label: 'label', children: 'children' }"
                placeholder="请选择到末级（房间）" filterable check-strictly style="width: 100%" @change="clearPicked"
              />
            </template>
            <template v-else>
              <div class="loc-box__label">调出部门 <b class="req">*</b></div>
              <el-select v-model="form.out_dept_id" filterable placeholder="请选择调出部门" style="width: 100%" @change="clearPicked">
                <el-option v-for="d in depts" :key="d.id" :label="d.org_name" :value="d.id" />
              </el-select>
            </template>
          </div>
          <div class="loc-box">
            <div class="loc-box__title">调入（去向）</div>
            <template v-if="form.transfer_type === 1">
              <div class="loc-box__label">调入仓库 <b class="req">*</b></div>
              <el-select v-model="form.in_warehouse_id" filterable placeholder="请选择调入仓库" style="width: 100%" @change="clearPicked">
                <el-option v-for="w in warehouses" :key="w.id" :label="w.warehouse_name" :value="w.id" :disabled="w.id === form.out_warehouse_id" />
              </el-select>
            </template>
            <template v-else-if="form.transfer_type === 2">
              <div class="loc-box__label">调入项目空间（末级） <b class="req">*</b></div>
              <el-tree-select
                v-model="form.in_project_id" :data="spaceTree" node-key="id"
                :props="{ label: 'label', children: 'children' }"
                placeholder="请选择到末级（房间）" filterable check-strictly style="width: 100%" @change="clearPicked"
              />
            </template>
            <template v-else>
              <div class="loc-box__label">调入部门 <b class="req">*</b></div>
              <el-select v-model="form.in_dept_id" filterable placeholder="请选择调入部门" style="width: 100%" @change="clearPicked">
                <el-option v-for="d in depts" :key="d.id" :label="d.org_name" :value="d.id" :disabled="d.id === form.out_dept_id" />
              </el-select>
            </template>
          </div>
        </div>

        <div class="sec-title mt-12">
          选择资产
          <span class="text-muted asset-hint">
            {{ form.transfer_type === 1 ? "限调出仓库在库资产" : form.transfer_type === 2 ? "限调出空间内资产（在库/领用中）" : "限调出部门资产（在库/领用中）" }}
          </span>
        </div>
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px; flex-wrap: wrap">
          <el-button type="primary" plain :disabled="!outLocReady" @click="openAssetSelect">选择资产</el-button>
          <span class="text-muted">已选 <b>{{ selectedAssets.length }}</b> 项</span>
          <el-select
            v-model="pickedGroup" placeholder="或：按组合包整包添加" clearable style="width: 240px"
            :disabled="!outLocReady" @change="onGroupPick"
          >
            <el-option v-for="g in groups" :key="g.id" :label="`${g.group_name}（${g.asset_count} 项）`" :value="g.id" />
          </el-select>
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
          <el-table-column label="调入后位置" width="130">
            <template #default="{ row }">
              <el-input v-model="row.location_detail" placeholder="使用位置" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="责任人" width="100">
            <template #default="{ row }">
              <el-select v-model="row.use_user_id" filterable placeholder="责任人" size="small">
                <el-option v-for="u in users" :key="u.id" :label="u.real_name" :value="u.id" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="责任部门" width="120">
            <template #default="{ row }">
              <el-select v-model="row.use_dept_id" filterable placeholder="责任部门" size="small">
                <el-option v-for="d in depts" :key="d.id" :label="d.org_name" :value="d.id" />
              </el-select>
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

    <!-- 资产选择弹窗（按调出维度 + 状态限定） -->
    <AssetSelectDialog
      v-model="assetSelectVisible"
      :title="assetSelectTitle"
      :allow-statuses="assetAllowStatuses"
      :preset="assetSelectPreset"
      :defaults="assetSelectDefaults"
      @confirm="onAssetConfirmed"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Search, Plus } from "@element-plus/icons-vue";
import { docApi, archiveApi, sysApi, assetApi, groupApi } from "../../api";
import AssetSelectDialog from "../../components/AssetSelectDialog.vue";
import { DOC_STATUS, fmtDate, fmtDateTime, todayStr, assetStatusName, fmtMoney } from "../../utils/constants";
import { loadFlowEnabled } from "../../utils/approval";
import ApprovalFlowPanel from "../../components/ApprovalFlowPanel.vue";

const TRANSFER_TYPE = { 1: "仓库调拨", 2: "项目空间调拨", 4: "部门调拨" };

const flowEnabled = ref(true);
const loading = ref(false);
const saving = ref(false);
const submitting = ref(false);
const rows = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const q = reactive({ keyword: "", status: null });

const warehouses = ref([]);
const spaceTree = ref([]);
const depts = ref([]);
const users = ref([]);

// 列表位置展示（按调拨类型取仓库/空间/部门名称）
const outLoc = (row) => row.out_space_name || row.out_dept_name || row.out_warehouse_name || "-";
const inLoc = (row) => row.in_space_name || row.in_dept_name || row.in_warehouse_name || "-";
const detailLoc = (d, side) => {
  if (d.transfer_type === 2) return d[`${side}_space_name`] || "-";
  if (d.transfer_type === 4) return d[`${side}_dept_name`] || "-";
  return d[`${side}_warehouse_name`] || "-";
};

async function load() {
  loading.value = true;
  try {
    const params = { page: page.value, page_size: pageSize.value };
    if (q.keyword) params.keyword = q.keyword;
    if (q.status !== null) params.status = q.status;
    const res = await docApi.transfers(params);
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
  detail.value = await docApi.transfer(row.id);
  const items = detail.value.items || [];
  detailItems.value = await Promise.all(
    items.map(async (i) => {
      try {
        const a = await assetApi.detail(i.asset_id);
        const user = i.use_user_id ? await sysApi.users({ page: 1, page_size: 1, keyword: i.use_user_id }) : null;
        const dept = depts.value.find((d) => d.id === i.use_dept_id);
        return {
          ...i,
          asset_code: a.asset_code,
          asset_name: a.asset_name,
          use_user_name: user?.records?.[0]?.real_name || "-",
          use_dept_name: dept?.org_name || "-",
        };
      } catch {
        return { ...i, asset_code: `#${i.asset_id}`, asset_name: "-", use_user_name: "-", use_dept_name: "-" };
      }
    })
  );
  detailVisible.value = true;
}

// ---- 新建 ----
const formVisible = ref(false);
const form = reactive({
  transfer_no: "",
  out_warehouse_id: null, in_warehouse_id: null,
  out_project_id: null, in_project_id: null,
  out_dept_id: null, in_dept_id: null,
  transfer_date: "", transfer_type: 1,
  remark: "",
});
const selectedAssets = ref([]);

// 调出维度是否已选（资产选择前置条件）
const outLocReady = computed(() => {
  if (form.transfer_type === 1) return !!form.out_warehouse_id;
  if (form.transfer_type === 2) return !!form.out_project_id;
  return !!form.out_dept_id;
});

function onTransferTypeChange() {
  form.out_warehouse_id = null;
  form.in_warehouse_id = null;
  form.out_project_id = null;
  form.in_project_id = null;
  form.out_dept_id = null;
  form.in_dept_id = null;
  clearPicked();
}
function clearPicked() {
  selectedAssets.value = [];
  pickedGroup.value = null;
}

// ---- 编号预览（自动生成，只读展示） ----
async function refreshNo() {
  try {
    const res = await docApi.nextDocNo("transfer");
    form.transfer_no = res.next_no;
  } catch {
    form.transfer_no = "";
  }
}

// ---- 组合包整包添加 ----
const groups = ref([]);
const pickedGroup = ref(null);
async function loadGroups() {
  try {
    const res = await groupApi.list({ page: 1, page_size: 100 });
    groups.value = (res.records || []).filter((g) => g.status === 1);
  } catch {
    groups.value = [];
  }
}
async function onGroupPick(gid) {
  if (!gid) return;
  const d = await groupApi.detail(gid);
  let inLoc = d.assets || [];
  if (form.transfer_type === 1) inLoc = inLoc.filter((a) => a.status === 1 && a.warehouse_id === form.out_warehouse_id);
  else if (form.transfer_type === 2) inLoc = inLoc.filter((a) => [1, 2].includes(a.status) && a.space_id === form.out_project_id);
  else inLoc = inLoc.filter((a) => [1, 2].includes(a.status) && a.use_dept_id === form.out_dept_id);
  const missing = (d.assets || []).length - inLoc.length;
  let added = 0;
  inLoc.forEach((a) => {
    if (!selectedAssets.value.some((x) => x.id === a.id)) {
      selectedAssets.value = [...selectedAssets.value, a];
      added++;
    }
  });
  if (added) ElMessage.success(`已整包添加 ${added} 项资产`);
  if (missing > 0) ElMessage.warning(`${missing} 项不在调出位置或非可调拨状态，已跳过`);
}

// ---- 资产选择弹窗（按调出维度限定） ----
const assetSelectVisible = ref(false);
const assetSelectPreset = ref([]);
const assetSelectDefaults = computed(() => {
  if (form.transfer_type === 1) return { warehouse_id: form.out_warehouse_id, status: 1 };
  if (form.transfer_type === 2) return { space_id: form.out_project_id };
  return { use_dept_id: form.out_dept_id };
});
const assetAllowStatuses = computed(() => (form.transfer_type === 1 ? [1] : [1, 2]));
const assetSelectTitle = computed(() => {
  const t = TRANSFER_TYPE[form.transfer_type] || "调拨";
  return `选择调出资产（${t}）`;
});
function openAssetSelect() {
  if (!outLocReady.value) return ElMessage.warning("请先选择调出位置");
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
    transfer_no: "",
    out_warehouse_id: null, in_warehouse_id: null,
    out_project_id: null, in_project_id: null,
    out_dept_id: null, in_dept_id: null,
    transfer_date: todayStr(), transfer_type: 1,
    remark: "",
  });
  selectedAssets.value = [];
  pickedGroup.value = null;
  formVisible.value = true;
  refreshNo();
}
function save(submit = false) {
  if (form.transfer_type === 1) {
    if (!form.out_warehouse_id || !form.in_warehouse_id) return ElMessage.warning("请选择调出/调入仓库");
    if (form.out_warehouse_id === form.in_warehouse_id) return ElMessage.warning("调入调出仓库不能相同");
  } else if (form.transfer_type === 2) {
    if (!form.out_project_id || !form.in_project_id) return ElMessage.warning("请选择调出/调入项目空间（末级）");
    if (form.out_project_id === form.in_project_id) return ElMessage.warning("调入调出项目空间不能相同");
  } else {
    if (!form.out_dept_id || !form.in_dept_id) return ElMessage.warning("请选择调出/调入部门");
    if (form.out_dept_id === form.in_dept_id) return ElMessage.warning("调入调出部门不能相同");
  }
  if (!selectedAssets.value.length) return ElMessage.warning("请选择调拨资产");
  saving.value = true;
  (async () => {
    try {
      const created = await docApi.createTransfer({
        transfer_type: form.transfer_type,
        out_warehouse_id: form.transfer_type === 1 ? form.out_warehouse_id : null,
        in_warehouse_id: form.transfer_type === 1 ? form.in_warehouse_id : null,
        out_project_id: form.transfer_type === 2 ? form.out_project_id : null,
        in_project_id: form.transfer_type === 2 ? form.in_project_id : null,
        out_dept_id: form.transfer_type === 4 ? form.out_dept_id : null,
        in_dept_id: form.transfer_type === 4 ? form.in_dept_id : null,
        transfer_date: form.transfer_date || null,
        remark: form.remark || null,
        items: selectedAssets.value.map((a) => ({
          asset_id: a.id,
          use_location: a.location_detail || null,
          use_user_id: a.use_user_id || null,
          use_dept_id: a.use_dept_id || null,
        })),
      });
      if (submit) {
        const res = await docApi.submit("transfer", created.id);
        ElMessage.success(res.manual ? "已提交，待手动审批通过" : "已提交审批，资产已锁定为「调拨中」");
      } else {
        ElMessage.success("调拨单已保存（草稿），编号自动生成");
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
      ? `提交后单据进入审批流并锁定资产，确认提交「${row.transfer_no || row.id}」？`
      : `提交后单据待手动审批，确认提交「${row.transfer_no || row.id}」？`;
    await ElMessageBox.confirm(tip, flowEnabled.value ? "提交审批" : "提交", { type: "warning" });
  } catch {
    return;
  }
  submitting.value = true;
  try {
    const res = await docApi.submit("transfer", row.id);
    ElMessage.success(res.manual ? "已提交，待手动审批通过" : "已提交审批，资产已锁定为「调拨中」");
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
  await docApi.manualApprove("transfer", row.id);
  ElMessage.success("已手动审批通过，单据已生效");
  load();
}
async function cancel(row) {
  try {
    await ElMessageBox.confirm("撤销后单据作废，资产恢复原状态，确认撤销？", "撤销", { type: "warning" });
  } catch {
    return;
  }
  await docApi.cancel("transfer", row.id);
  ElMessage.success("已撤销");
  load();
}

// 空间树（仅末级可选）
function toSpaceTree(nodes) {
  return (nodes || []).map((n) => {
    const children = toSpaceTree(n.children);
    return {
      id: n.id,
      label: n.space_name,
      children: children.length ? children : undefined,
      disabled: children.length > 0,
    };
  });
}

onMounted(async () => {
  flowEnabled.value = await loadFlowEnabled("transfer");
  // 基础数据加载失败不阻塞列表（如组织接口被拒时页面仍可用）
  const [ws, spaces, os, us] = await Promise.allSettled([
    archiveApi.warehouses(),
    archiveApi.spaces(),
    sysApi.orgs(),
    sysApi.users({ page: 1, page_size: 200 }),
  ]);
  if (ws.status === "fulfilled") warehouses.value = ws.value;
  if (spaces.status === "fulfilled") spaceTree.value = toSpaceTree(spaces.value);
  if (os.status === "fulfilled") depts.value = os.value.filter((o) => o.org_type === 4 && o.status === 1);
  if (us.status === "fulfilled") users.value = (us.value.records || []).filter((u) => u.status === 1);
  loadGroups();
  load();
});
</script>

<style scoped>
.table-card { flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
.loc-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 4px; }
.loc-box { border: 1px solid var(--el-border-color-lighter); border-radius: 8px; padding: 12px 14px; background: var(--el-fill-color-lighter); }
.loc-box__title { font-size: 13px; font-weight: 600; margin-bottom: 8px; }
.loc-box__label { font-size: 12px; color: var(--el-text-color-secondary); margin-bottom: 4px; }
.req { color: var(--el-color-danger); }
.asset-hint { font-size: 12px; font-weight: 400; margin-left: 8px; }
</style>
