<template>
  <el-dialog
    :model-value="modelValue"
    :title="title"
    width="900px"
    top="6vh"
    destroy-on-close
    @update:model-value="$emit('update:modelValue', $event)"
    @open="onOpen"
  >
    <!-- 维度筛选 -->
    <div class="as-filter">
      <el-input v-model="q.keyword" placeholder="编码 / 名称 / 规格" clearable style="width: 180px" @keyup.enter="reload" />
      <el-select v-model="q.status" placeholder="状态" clearable style="width: 118px" @change="reload">
        <el-option v-for="s in ASSET_STATUS" :key="s.value" :label="s.label" :value="s.value" />
      </el-select>
      <el-select v-model="q.org_id" placeholder="核算公司" clearable filterable style="width: 150px" @change="reload">
        <el-option v-for="o in orgOptions" :key="o.id" :label="o.org_name" :value="o.id" />
      </el-select>
      <el-select v-model="q.project_id" placeholder="项目" clearable filterable style="width: 150px" @change="reload">
        <el-option v-for="p in projects" :key="p.id" :label="p.org_name" :value="p.id" />
      </el-select>
      <el-select v-model="q.warehouse_id" placeholder="仓库" clearable filterable style="width: 150px" @change="reload">
        <el-option v-for="w in warehouses" :key="w.id" :label="w.warehouse_name" :value="w.id" />
      </el-select>
      <el-select v-model="q.space_id" placeholder="项目空间" clearable filterable style="width: 160px" @change="reload">
        <el-option v-for="sp in spaceOptions" :key="sp.id" :label="sp.space_name" :value="sp.id" />
      </el-select>
      <el-select v-model="q.use_dept_id" placeholder="责任部门" clearable filterable style="width: 140px" @change="reload">
        <el-option v-for="d in deptOptions" :key="d.id" :label="d.org_name" :value="d.id" />
      </el-select>
      <el-button type="primary" plain @click="reload">查询</el-button>
      <el-button @click="resetQ">重置</el-button>
    </div>

    <!-- 已选摘要 -->
    <div class="as-summary">
      <span>已选 <b class="num">{{ selectedMap.size }}</b> 项</span>
      <el-button v-if="selectedMap.size" link type="danger" size="small" @click="clearAll">清空已选</el-button>
      <span v-if="!allowAll" class="as-tip text-muted">（仅{{ allowStatusText }}可选）</span>
    </div>

    <!-- 资产表（多选 + 跨页保留勾选） -->
    <el-table
      ref="tableRef"
      :data="rows"
      v-loading="loading"
      row-key="id"
      height="380"
      @select="onSelect"
      @select-all="onSelectAll"
    >
      <el-table-column type="selection" width="44" :reserve-selection="true" :selectable="selectable" />
      <el-table-column prop="asset_code" label="资产编码" width="150" />
      <el-table-column prop="asset_name" label="资产名称" min-width="150" show-overflow-tooltip />
      <el-table-column prop="category_name" label="分类" width="104" show-overflow-tooltip />
      <el-table-column prop="spec" label="规格" min-width="130" show-overflow-tooltip />
      <el-table-column prop="org_name" label="核算公司" width="120" show-overflow-tooltip />
      <el-table-column prop="project_name" label="项目" width="120" show-overflow-tooltip />
      <el-table-column prop="warehouse_name" label="仓库" width="100" show-overflow-tooltip />
      <el-table-column label="状态" width="84" align="center">
        <template #default="{ row }">
          <el-tag size="small" :type="statusTag(row.status)">{{ assetStatusName(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="原值" width="104" align="right">
        <template #default="{ row }"><span class="num">{{ fmtMoney(row.price) }}</span></template>
      </el-table-column>
      <el-table-column label="净值" width="104" align="right">
        <template #default="{ row }"><span class="num">{{ fmtMoney(row.net_value) }}</span></template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div class="as-pager">
      <span class="text-muted">共 {{ total }} 项资产</span>
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="sizes, prev, pager, next"
        background
        @current-change="load"
        @size-change="() => { page = 1; load(); }"
      />
    </div>

    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :disabled="!selectedMap.size" @click="confirm">确定（{{ selectedMap.size }} 项）</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, nextTick, reactive, ref } from "vue";
import { assetApi, archiveApi, sysApi } from "../api";
import { ASSET_STATUS, assetStatusName, fmtMoney } from "../utils/constants";

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: "选择资产" },
  // 允许勾选的资产状态（业务规则：报废排除 5/6，调拨/出库限定在库 1 等）
  allowStatuses: { type: Array, default: () => [0, 1, 2, 3, 4] },
  // 预设已选（资产对象数组），再次打开时回显
  preset: { type: Array, default: () => [] },
  // 初始筛选值
  defaults: { type: Object, default: () => ({}) },
});
const emit = defineEmits(["update:modelValue", "confirm"]);

const tableRef = ref();
const loading = ref(false);
const rows = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const q = reactive({ keyword: "", status: null, org_id: null, project_id: null, warehouse_id: null, space_id: null, use_dept_id: null });

const orgOptions = ref([]);
const warehouses = ref([]);
const projects = ref([]);
const spaceOptions = ref([]);
const deptOptions = ref([]);

const allowAll = computed(() => props.allowStatuses.length >= ASSET_STATUS.length);
const allowStatusText = computed(() => props.allowStatuses.map((s) => assetStatusName(s)).join("/"));

const selectedMap = reactive(new Map()); // id -> 资产对象（跨页汇总，reactive 保证 .size 响应式更新）

const selectable = (row) => props.allowStatuses.includes(row.status);

function statusTag(status) {
  return status === 1 ? "success" : status === 2 ? "primary" : status >= 5 ? "danger" : "info";
}

// 用户勾选（@select / @select-all 仅在用户交互时触发，程序化回显不会误触）
function onSelect(selection, row) {
  if (selection.includes(row)) selectedMap.set(row.id, row);
  else selectedMap.delete(row.id);
}
function onSelectAll(selection) {
  const selIds = new Set(selection.map((r) => r.id));
  const currentSelectable = rows.value.filter((r) => props.allowStatuses.includes(r.status));
  const isSelectAll = currentSelectable.length > 0 && currentSelectable.every((r) => selIds.has(r.id));
  currentSelectable.forEach((r) => {
    if (isSelectAll) selectedMap.set(r.id, r);
    else selectedMap.delete(r.id);
  });
}

async function load() {
  loading.value = true;
  try {
    const params = { page: page.value, page_size: pageSize.value };
    if (q.keyword) params.keyword = q.keyword;
    if (q.status != null) params.status = q.status;
    if (q.org_id) params.org_id = q.org_id;
    if (q.project_id) params.project_id = q.project_id;
    if (q.warehouse_id) params.warehouse_id = q.warehouse_id;
    if (q.space_id) params.space_id = q.space_id;
    if (q.use_dept_id) params.use_dept_id = q.use_dept_id;
    const res = await assetApi.list(params);
    rows.value = res.records || [];
    total.value = res.total || 0;
    // 回显当前页已选（reserve-selection 跨页保留；程序勾选不触发 @select，不会污染 selectedMap）
    await nextTick();
    const selectedIds = new Set(selectedMap.keys());
    rows.value.forEach((r) => {
      if (selectedIds.has(r.id) && props.allowStatuses.includes(r.status)) {
        tableRef.value?.toggleRowSelection(r, true);
      }
    });
  } finally {
    loading.value = false;
  }
}

function reload() {
  page.value = 1;
  load();
}
function resetQ() {
  Object.assign(q, { keyword: "", status: null, org_id: null, project_id: null, warehouse_id: null, space_id: null, use_dept_id: null });
  reload();
}

async function onOpen() {
  // 初始化筛选（支持调用方默认值，如调拨限定在库 + 调出仓库/空间/部门）
  Object.assign(q, {
    keyword: "", status: null, org_id: null, project_id: null, warehouse_id: null, space_id: null, use_dept_id: null,
    ...(props.defaults || {}),
  });
  // 回显预设已选
  selectedMap.clear();
  (props.preset || []).forEach((a) => selectedMap.set(a.id, a));
  page.value = 1;
  if (!orgOptions.value.length) await loadOptions();
  await load();
}

async function loadOptions() {
  const [orgs, whs, spaces] = await Promise.all([sysApi.orgs(), archiveApi.warehouses(), archiveApi.spaces()]);
  orgOptions.value = orgs.filter((o) => o.org_type <= 3 || o.is_accounting);
  projects.value = orgs.filter((o) => o.org_type === 3);
  warehouses.value = whs;
  deptOptions.value = orgs.filter((o) => o.org_type === 4 && o.status === 1);
  // 空间树拍平为列表供筛选（后端按 space_id 精确匹配）
  const flat = [];
  const walk = (list) => (list || []).forEach((s) => { flat.push(s); walk(s.children); });
  walk(spaces);
  spaceOptions.value = flat;
}

function clearAll() {
  selectedMap.clear();
  tableRef.value?.clearSelection();
}

function confirm() {
  emit("confirm", Array.from(selectedMap.values()));
  emit("update:modelValue", false);
}
</script>

<style scoped>
.as-filter { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.as-summary { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; font-size: 13px; }
.as-tip { font-size: 12px; }
.as-pager { display: flex; align-items: center; justify-content: space-between; margin-top: 12px; }
</style>
