<template>
  <div class="page">
    <div class="page__head">
      <h1 class="page__title">盘点任务</h1>
      <span class="page__sub">账面快照冻结 · 差异率自动计算 · 三类报表输出</span>
    </div>

    <div class="card table-card">
      <div class="filter-bar">
        <el-input v-model="q.keyword" placeholder="任务号/名称" clearable :prefix-icon="Search" @keyup.enter="load" />
        <el-select v-model="q.status" placeholder="任务状态" clearable @change="page = 1, load()">
          <el-option v-for="(s, k) in CHECK_STATUS" :key="k" :label="s.label" :value="Number(k)" />
        </el-select>
        <el-select v-model="q.check_type" placeholder="盘点类型" clearable @change="page = 1, load()">
          <el-option v-for="(t, k) in CHECK_TYPE_LABEL" :key="k" :label="t" :value="Number(k)" />
        </el-select>
        <el-button type="primary" plain @click="load">查询</el-button>
        <el-button @click="reset">重置</el-button>
        <el-button :icon="Iphone" style="margin-left: auto" @click="openMobile">移动端扫码盘点</el-button>
        <el-button v-perm="'check:create'" type="primary" :icon="Plus" @click="openCreate">新建盘点任务</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" height="100%">
        <el-table-column prop="task_no" label="任务号" width="140" fixed />
        <el-table-column prop="task_name" label="任务名称" min-width="170" show-overflow-tooltip />
        <el-table-column label="类型" width="90" align="center">
          <template #default="{ row }">{{ CHECK_TYPE_LABEL[row.check_type] || "-" }}</template>
        </el-table-column>
        <el-table-column label="盘点范围" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ scopeText(row) }}</template>
        </el-table-column>
        <el-table-column prop="book_total" label="账面数" width="80" align="right" />
        <el-table-column label="差异率" width="90" align="right">
          <template #default="{ row }">
            <span class="num" :class="{ 'diff-warn': row.diff_rate > 0.02 }">{{ pct(row.diff_rate) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="96" align="center">
          <template #default="{ row }">
            <el-tag :type="CHECK_STATUS[row.status]?.type" size="small">{{ CHECK_STATUS[row.status]?.label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="plan_start" label="计划开始" width="100">
          <template #default="{ row }">{{ fmtDate(row.plan_start) }}</template>
        </el-table-column>
        <el-table-column label="完成时间" width="145">
          <template #default="{ row }">{{ fmtDateTime(row.finish_time) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 1" link type="primary" size="small" @click="openExec(row)">执行盘点</el-button>
            <el-button v-else link type="primary" size="small" @click="openExec(row)">查看明细</el-button>
            <el-button v-if="row.status === 1" link type="success" size="small" @click="finish(row)">完成</el-button>
            <el-button v-if="row.status === 2" link type="warning" size="small" @click="handleDiff(row)">差异处理</el-button>
            <el-dropdown trigger="click" @command="(cmd) => exportReport(row, cmd)">
              <el-button link type="primary" size="small">
                报表<el-icon><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="detail">盘点明细表</el-dropdown-item>
                  <el-dropdown-item command="diff">盘盈盘亏差异表</el-dropdown-item>
                  <el-dropdown-item command="summary">盘点汇总表</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <span class="text-muted">共 {{ total }} 个盘点任务</span>
        <el-pagination
          v-model:current-page="page" v-model:page-size="pageSize" :total="total"
          :page-sizes="[20, 50]" layout="sizes, prev, pager, next" background
          @current-change="load" @size-change="() => { page = 1; load(); }"
        />
      </div>
    </div>

    <!-- 新建任务 -->
    <el-dialog v-model="formVisible" title="新建盘点任务" width="620px" destroy-on-close>
      <el-alert type="info" :closable="false" class="mb-12"
        title="创建时冻结范围内全部在管资产的账面快照（含状态与位置），作为差异比对基准。" />
      <el-form :model="form" label-width="86px">
        <el-form-item label="任务名称" required>
          <el-input v-model="form.task_name" maxlength="200" placeholder="如：2026年度年中大盘点" />
        </el-form-item>
        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="盘点类型" required>
              <el-select v-model="form.check_type">
                <el-option v-for="(t, k) in CHECK_TYPE_LABEL" :key="k" :label="t" :value="Number(k)" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="盘点范围" required>
              <el-select v-model="form.scope_type" @change="form.scope_id = null">
                <el-option label="公司" :value="1" />
                <el-option label="仓库" :value="3" />
                <el-option label="空间" :value="4" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="范围对象" required>
              <el-select v-model="form.scope_id" filterable>
                <el-option
                  v-for="o in scopeOptions" :key="o.id" :label="o.name" :value="o.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="盘点人">
              <el-select v-model="form.checker_ids" filterable clearable>
                <el-option v-for="u in users" :key="u.id" :label="u.real_name" :value="String(u.id)" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="计划开始">
              <el-date-picker v-model="form.plan_start" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="计划结束">
              <el-date-picker v-model="form.plan_end" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">创建并冻结快照</el-button>
      </template>
    </el-dialog>

    <!-- 执行抽屉 -->
    <el-drawer v-model="execVisible" size="72%" :title="`盘点执行 · ${curTask?.task_name || ''}`" destroy-on-close>
      <template #header>
        <div>
          <div style="font-size: 16px">{{ curTask?.task_name }}</div>
          <div class="num" style="font-size: 12px; color: var(--ink-3)">
            {{ curTask?.task_no }} · 账面 {{ curTask?.book_total }} 项
          </div>
        </div>
      </template>

      <!-- 汇总条 -->
      <div v-if="summary" class="summary-strip">
        <div class="ss-item"><span>已盘</span><b class="num">{{ summary.checked }}/{{ summary.book_total }}</b></div>
        <div class="ss-item"><span>正常</span><b class="num ok">{{ summary.normal }}</b></div>
        <div class="ss-item"><span>盘盈</span><b class="num warn">{{ summary.surplus }}</b></div>
        <div class="ss-item"><span>盘亏</span><b class="num danger">{{ summary.loss }}</b></div>
        <div class="ss-item"><span>位置异常</span><b class="num">{{ summary.position_diff }}</b></div>
        <div class="ss-item"><span>未盘</span><b class="num muted">{{ summary.unchecked }}</b></div>
        <div class="ss-item"><span>差异率</span><b class="num" :class="Number(summary.diff_rate) > 0.02 ? 'danger' : 'ok'">{{ pct(summary.diff_rate) }}</b></div>
        <div class="ss-item" v-if="curTask.status === 1">
          <el-button type="primary" size="small" @click="finish(curTask)">完成盘点</el-button>
        </div>
        <div class="ss-item" v-if="curTask.status === 1">
          <el-button type="warning" plain size="small" @click="openSurplus">登记盘盈资产</el-button>
        </div>
        <div class="ss-item" v-if="curTask.status === 2">
          <el-button type="warning" size="small" @click="handleDiff(curTask)">一键差异处理</el-button>
        </div>
      </div>

      <!-- 明细筛选 -->
      <div class="filter-bar" style="padding-left: 0">
        <el-input v-model="iq.keyword" placeholder="编码/名称" clearable style="width: 160px" @keyup.enter="loadItems" />
        <el-select v-model="iq.check_result" placeholder="盘点结果" clearable style="width: 130px" @change="loadItems">
          <el-option v-for="(r, k) in CHECK_RESULT" :key="k" :label="r.label" :value="Number(k)" />
        </el-select>
        <el-checkbox v-model="iq.only_unchecked" label="只看未盘" @change="loadItems" />
        <el-button type="primary" plain size="default" @click="loadItems">查询</el-button>
      </div>

      <el-table :data="itemRows" v-loading="itemLoading" height="480">
        <el-table-column prop="asset_code" label="资产编码" width="160" />
        <el-table-column prop="asset_name" label="资产名称" min-width="150" show-overflow-tooltip />
        <el-table-column prop="category_name" label="分类" width="100" />
        <el-table-column label="账面位置" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ row.book_location || "-" }}</template>
        </el-table-column>
        <el-table-column label="结果" width="90" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.check_result" :type="CHECK_RESULT[row.check_result]?.type" size="small">
              {{ CHECK_RESULT[row.check_result]?.label }}
            </el-tag>
            <span v-else class="text-muted">未盘</span>
          </template>
        </el-table-column>
        <el-table-column label="实盘位置" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.actual_location || "-" }}</template>
        </el-table-column>
        <el-table-column label="盘点时间" width="145">
          <template #default="{ row }">{{ fmtDateTime(row.check_time) }}</template>
        </el-table-column>
        <el-table-column v-if="curTask.status === 1" label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="success" size="small" @click="record(row, 1)">正常</el-button>
            <el-button link type="danger" size="small" @click="record(row, 3)">盘亏</el-button>
            <el-button link type="warning" size="small" @click="openPosDiff(row)">位置异常</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager" style="border: none; background: transparent; padding-left: 0">
        <span class="text-muted">共 {{ itemTotal }} 项</span>
        <el-pagination
          v-model:current-page="itemPage" v-model:page-size="itemPageSize" :total="itemTotal"
          :page-sizes="[20, 50, 100]" layout="sizes, prev, pager, next" background
          @current-change="loadItems" @size-change="() => { itemPage = 1; loadItems(); }"
        />
      </div>
    </el-drawer>

    <!-- 位置异常 -->
    <el-dialog v-model="posVisible" title="记录位置异常" width="480px" destroy-on-close>
      <el-form label-width="90px">
        <el-form-item label="资产">
          <span>{{ curItem?.asset_code }} {{ curItem?.asset_name }}</span>
        </el-form-item>
        <el-form-item label="账面位置">
          <span class="text-muted">{{ curItem?.book_location || "-" }}</span>
        </el-form-item>
        <el-form-item label="实盘位置" required>
          <el-input v-model="posForm.actual_location" placeholder="如：云锦雅苑-样板间B-主卧" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="posVisible = false">取消</el-button>
        <el-button type="primary" @click="savePosDiff">确认</el-button>
      </template>
    </el-dialog>

    <!-- 盘盈登记 -->
    <el-dialog v-model="surplusVisible" title="登记盘盈资产" width="520px" destroy-on-close>
      <el-alert type="warning" :closable="false" class="mb-12"
        title="盘盈资产将在差异处理时自动建档入库（盘盈入库）。" />
      <el-form label-width="90px">
        <el-form-item label="资产名称" required>
          <el-input v-model="surplusForm.surplus_name" maxlength="200" placeholder="如实物的名称" />
        </el-form-item>
        <el-form-item label="分类">
          <el-tree-select
            v-model="surplusForm.surplus_category_id" :data="categoryTree" node-key="id"
            :props="{ label: 'category_name', children: 'children' }" check-strictly
            placeholder="默认「其他」根类" style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="估值">
          <el-input-number v-model="surplusForm.surplus_price" :min="0" :precision="2" :controls="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="实盘位置">
          <el-input v-model="surplusForm.actual_location" placeholder="当前位置" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="surplusVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveSurplus">登记</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Search, Plus, ArrowDown, Iphone } from "@element-plus/icons-vue";
import { checkApi, archiveApi, sysApi, download } from "../../api";
import {
  CHECK_STATUS, CHECK_RESULT, CHECK_TYPE_LABEL, fmtDate, fmtDateTime, pct, todayStr,
} from "../../utils/constants";

const loading = ref(false);
const saving = ref(false);
const rows = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const q = reactive({ keyword: "", status: null, check_type: null });

const orgs = ref([]);
const warehouses = ref([]);
const spaces = ref([]);
const users = ref([]);
const categories = ref([]);

const scopeOptions = computed(() => {
  if (form.scope_type === 1) return orgs.value.map((o) => ({ id: o.id, name: o.org_name }));
  if (form.scope_type === 3) return warehouses.value.map((w) => ({ id: w.id, name: w.warehouse_name }));
  if (form.scope_type === 4) return spaces.value.map((s) => ({ id: s.id, name: s.space_name }));
  return [];
});
const categoryTree = computed(() => {
  const roots = categories.value.filter((c) => !c.parent_id || c.parent_id === 0);
  return roots.map((r) => ({ ...r, children: categories.value.filter((c) => c.parent_id === r.id) }));
});

function scopeText(row) {
  const t = { 1: "公司", 2: "项目", 3: "仓库", 4: "空间", 5: "部门" }[row.scope_type] || "-";
  let name = row.scope_id;
  if (row.scope_type === 1) name = orgs.value.find((o) => o.id === row.scope_id)?.org_name;
  if (row.scope_type === 3) name = warehouses.value.find((w) => w.id === row.scope_id)?.warehouse_name;
  if (row.scope_type === 4) name = spaces.value.find((s) => s.id === row.scope_id)?.space_name;
  return `${t} · ${name || row.scope_id}`;
}

async function load() {
  loading.value = true;
  try {
    const params = { page: page.value, page_size: pageSize.value };
    if (q.keyword) params.keyword = q.keyword;
    if (q.status !== null) params.status = q.status;
    if (q.check_type !== null) params.check_type = q.check_type;
    const res = await checkApi.tasks(params);
    rows.value = res.records;
    total.value = res.total;
  } finally {
    loading.value = false;
  }
}
function reset() {
  Object.assign(q, { keyword: "", status: null, check_type: null });
  page.value = 1;
  load();
}

function openMobile() {
  window.open("/m/stocktake", "_blank");
}

// ---- 新建 ----
const formVisible = ref(false);
const form = reactive({ task_name: "", check_type: 1, scope_type: 1, scope_id: null, plan_start: "", plan_end: "", checker_ids: null, remark: "" });
function openCreate() {
  Object.assign(form, {
    task_name: "", check_type: 1, scope_type: 1,
    scope_id: orgs.value[0]?.id ?? null,
    plan_start: todayStr(),
    plan_end: "", checker_ids: null, remark: "",
  });
  formVisible.value = true;
}
async function save() {
  if (!form.task_name.trim()) return ElMessage.warning("请填写任务名称");
  if (!form.scope_id) return ElMessage.warning("请选择盘点范围对象");
  saving.value = true;
  try {
    await checkApi.createTask({ ...form });
    ElMessage.success("盘点任务已创建，账面快照已冻结");
    formVisible.value = false;
    load();
  } finally {
    saving.value = false;
  }
}

// ---- 执行 ----
const execVisible = ref(false);
const curTask = ref({});
const summary = ref(null);
const itemRows = ref([]);
const itemTotal = ref(0);
const itemPage = ref(1);
const itemPageSize = ref(50);
const itemLoading = ref(false);
const iq = reactive({ keyword: "", check_result: null, only_unchecked: false });

async function openExec(row) {
  curTask.value = row;
  execVisible.value = true;
  Object.assign(iq, { keyword: "", check_result: null, only_unchecked: false });
  itemPage.value = 1;
  await Promise.all([loadItems(), loadSummary()]);
}
async function loadSummary() {
  try {
    summary.value = await checkApi.summary(curTask.value.id);
  } catch {
    summary.value = null;
  }
}
async function loadItems() {
  itemLoading.value = true;
  try {
    const params = { page: itemPage.value, page_size: itemPageSize.value };
    if (iq.keyword) params.keyword = iq.keyword;
    if (iq.check_result !== null) params.check_result = iq.check_result;
    if (iq.only_unchecked) params.only_unchecked = true;
    const res = await checkApi.items(curTask.value.id, params);
    itemRows.value = res.records;
    itemTotal.value = res.total;
  } finally {
    itemLoading.value = false;
  }
}

async function record(row, result) {
  await checkApi.record(row.id, { check_result: result, actual_location: row.book_location });
  ElMessage.success(result === 1 ? "已记录正常" : "已记录盘亏");
  loadItems();
  loadSummary();
}

// 位置异常
const posVisible = ref(false);
const curItem = ref({});
const posForm = reactive({ actual_location: "" });
function openPosDiff(row) {
  curItem.value = row;
  posForm.actual_location = "";
  posVisible.value = true;
}
async function savePosDiff() {
  if (!posForm.actual_location.trim()) return ElMessage.warning("请填写实盘位置");
  await checkApi.record(curItem.value.id, { check_result: 4, actual_location: posForm.actual_location });
  ElMessage.success("已记录位置异常");
  posVisible.value = false;
  loadItems();
  loadSummary();
}

// 盘盈登记
const surplusVisible = ref(false);
const surplusForm = reactive({ surplus_name: "", surplus_category_id: null, surplus_price: null, actual_location: "" });
function openSurplus() {
  Object.assign(surplusForm, { surplus_name: "", surplus_category_id: null, surplus_price: null, actual_location: "" });
  surplusVisible.value = true;
}
async function saveSurplus() {
  if (!surplusForm.surplus_name.trim()) return ElMessage.warning("请填写盘盈资产名称");
  saving.value = true;
  try {
    await checkApi.surplus(curTask.value.id, surplusForm);
    ElMessage.success("盘盈资产已登记");
    surplusVisible.value = false;
    loadItems();
    loadSummary();
  } finally {
    saving.value = false;
  }
}

// 完成盘点
async function finish(row) {
  try {
    await ElMessageBox.confirm(
      "完成前请确保范围内资产已全部实盘（可分批）。完成后自动比对账实并计算差异率，差异率 > 2% 将标记复盘。",
      "完成盘点", { type: "warning", confirmButtonText: "确认完成" }
    );
  } catch {
    return;
  }
  const res = await checkApi.finish(row.id);
  await ElMessageBox.alert(
    `账面 ${res.total} 项：正常 ${res.normal} · 盘盈 ${res.surplus} · 盘亏 ${res.loss} · 位置异常 ${res.position_diff}<br/>
     差异率 <b>${res.diff_rate != null ? (res.diff_rate * 100).toFixed(2) : "-"}%</b>${res.need_review ? " —— 超过 2%，已标记复盘！" : ""}`,
    "盘点结果", { dangerouslyUseHTMLString: true, type: res.need_review ? "warning" : "success" }
  );
  execVisible.value = false;
  load();
}

// 差异处理
async function handleDiff(row) {
  try {
    await ElMessageBox.confirm(
      "差异处理将执行：盘盈资产自动建档入库、盘亏资产核销出库、位置异常资产更新账面位置。确认处理？",
      "差异处理", { type: "warning", confirmButtonText: "确认处理" }
    );
  } catch {
    return;
  }
  await checkApi.handleDiff(row.id);
  ElMessage.success("差异处理完成，任务已关闭");
  execVisible.value = false;
  load();
}

// 报表导出
async function exportReport(row, type) {
  const names = { detail: "盘点明细表", diff: "盘盈盘亏差异表", summary: "盘点汇总表" };
  await download(
    `/check-tasks/${row.id}/export?type=${type}`,
    `${names[type]}_${row.task_no}.xlsx`
  );
}

onMounted(async () => {
  const [os, ws, sps, us, cs] = await Promise.all([
    sysApi.orgs(),
    archiveApi.warehouses(),
    archiveApi.spaces({ page: 1, page_size: 500 }),
    sysApi.users({ page: 1, page_size: 200 }),
    archiveApi.categories(),
  ]);
  orgs.value = os;
  warehouses.value = ws;
  spaces.value = sps.records || sps;
  users.value = us.records;
  categories.value = cs;
  load();
});
</script>

<style scoped>
.table-card { flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
.diff-warn { color: var(--danger); font-weight: 600; }

.summary-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  background: linear-gradient(135deg, #fbf8f1, #f6efe0);
  border: 1px solid var(--gold-line);
  border-radius: var(--radius);
  padding: 10px 14px;
  margin-bottom: 12px;
}
.ss-item { display: flex; align-items: baseline; gap: 6px; font-size: 12px; color: var(--ink-2); }
.ss-item b { font-size: 15px; font-weight: 700; }
.ss-item .ok { color: var(--ok); }
.ss-item .warn { color: var(--warn); }
.ss-item .danger { color: var(--danger); }
.ss-item .muted { color: var(--ink-3); }
.ss-item .el-button { margin-left: 8px; }
.mb-12 { margin-bottom: 12px; }
</style>
