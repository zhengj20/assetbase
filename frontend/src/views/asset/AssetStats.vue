<template>
  <div class="page">
    <div class="page__head">
      <h1 class="page__title">资产统计</h1>
      <span class="page__sub">集团 → 公司 → 项目 → 部门 层级归口 · 点击左侧节点查看该级全部明细</span>
    </div>

    <!-- 顶部统计汇总 -->
    <div class="kpis">
      <div class="card kpi">
        <div class="kpi__label">资产总数</div>
        <div class="kpi__value num">{{ summary.count }}</div>
        <div class="kpi__foot">高值资产 {{ summary.high_value }} 项</div>
      </div>
      <div class="card kpi">
        <div class="kpi__label">资产原值</div>
        <div class="kpi__value num"><span class="money">{{ fmtMoney(summary.orig_value) }}</span></div>
        <div class="kpi__foot">{{ dim === "org" ? "全数据范围合计" : "已挂靠空间的资产合计" }}</div>
      </div>
      <div class="card kpi">
        <div class="kpi__label">资产净值</div>
        <div class="kpi__value num"><span class="money">{{ fmtMoney(summary.net_value) }}</span></div>
        <div class="kpi__foot">扣累计折旧后</div>
      </div>
      <div class="card kpi">
        <div class="kpi__label">当前选中</div>
        <div class="kpi__value num">
          <template v-if="selected">{{ sel.count }} 项</template>
          <template v-else>全部</template>
        </div>
        <div class="kpi__foot" v-if="selected">
          原值 <span class="money">{{ fmtMoney(sel.value) }}</span> · 净值 <span class="money">{{ fmtMoney(sel.net_value) }}</span>
        </div>
        <div class="kpi__foot" v-else>点击左侧节点下钻</div>
      </div>
    </div>

    <div class="body">
      <!-- 左侧：维度树（组织维度 / 空间维度） -->
      <div class="card tree-card">
        <div class="tree-card__dims">
          <el-radio-group v-model="dim" size="small" @change="onDimChange">
            <el-radio-button value="org">组织维度</el-radio-button>
            <el-radio-button value="space">空间维度</el-radio-button>
          </el-radio-group>
        </div>
        <div class="tree-card__title">{{ dim === "org" ? "集团 → 公司 → 项目 → 部门" : "项目 → 售楼处/样板间 → 房间" }}</div>
        <div class="tree-card__all" :class="{ on: !selected }" @click="clearNode">
          <span>全部资产</span>
          <span class="num">{{ summary.count }} 项</span>
        </div>
        <el-scrollbar class="tree-card__scroll">
          <el-tree
            v-loading="treeLoading"
            :key="dim"
            :data="tree"
            node-key="key"
            :props="{ label: dim === 'org' ? 'org_name' : 'name', children: 'children' }"
            highlight-current
            default-expand-all
            :expand-on-click-node="false"
            :current-node-key="selected ? selected.key : undefined"
            @node-click="onNodeClick"
          >
            <template #default="{ data }">
              <span class="tnode">
                <span class="tnode__name">
                  <span class="tnode__type" :class="nodeTypeClass(data)">{{ nodeTypeShort(data) }}</span>
                  {{ data.org_name || data.name }}
                </span>
                <span class="tnode__meta num">{{ data.count }} 项</span>
              </span>
            </template>
          </el-tree>
        </el-scrollbar>
      </div>

      <!-- 右侧：选中范围明细（同台账口径） -->
      <div class="card detail-card">
        <div class="filter-bar">
          <span class="detail-scope">
            {{ selected ? `「${selected.org_name || selected.name}」及下级` : "全部资产" }}
          </span>
          <el-input v-model="q.keyword" placeholder="名称/规格/品牌" clearable style="width: 200px" @keyup.enter="search" @clear="search" />
          <el-select v-model="q.status" placeholder="资产状态" clearable style="width: 140px" @change="search">
            <el-option v-for="s in ASSET_STATUS" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
          <el-button type="primary" plain @click="search">查询</el-button>
        </div>

        <el-table :data="rows" v-loading="loading" height="100%" class="flex-table">
          <el-table-column prop="asset_code" label="资产编码" width="170">
            <template #default="{ row }">
              <router-link class="code-link num" :to="`/asset/list?focus=${row.id}`">{{ row.asset_code }}</router-link>
            </template>
          </el-table-column>
          <el-table-column prop="asset_name" label="资产名称" min-width="170" show-overflow-tooltip />
          <el-table-column prop="category_name" label="分类" width="110" />
          <el-table-column label="状态" width="86" align="center">
            <template #default="{ row }">
              <span class="st" :class="`st--${row.status}`">{{ assetStatusName(row.status) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="原值" width="110" align="right">
            <template #default="{ row }"><span class="money">{{ fmtMoney(row.price) }}</span></template>
          </el-table-column>
          <el-table-column label="净值" width="110" align="right">
            <template #default="{ row }"><span class="num">{{ fmtMoney(row.net_value) }}</span></template>
          </el-table-column>
          <el-table-column prop="org_name" label="核算公司" width="130" show-overflow-tooltip />
          <el-table-column prop="project_name" label="项目" width="130" show-overflow-tooltip />
          <el-table-column prop="use_dept_name" label="责任部门" width="120" show-overflow-tooltip />
          <el-table-column prop="use_user_name" label="责任人" width="84" />
          <el-table-column prop="buy_date" label="购置日期" width="102" />
        </el-table>

        <div class="pager">
          <span class="text-muted">共 {{ total }} 项资产</span>
          <el-pagination
            v-model:current-page="page"
            v-model:page-size="pageSize"
            :total="total"
            :page-sizes="[20, 50, 100, 200]"
            layout="sizes, prev, pager, next, jumper"
            background
            @current-change="loadDetail"
            @size-change="() => { page = 1; loadDetail(); }"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { assetApi } from "../../api";
import { ASSET_STATUS, assetStatusName, fmtMoney } from "../../utils/constants";

const TYPE_SHORT = { 1: "集", 2: "司", 3: "项", 4: "部", 5: "点" };
const SPACE_SHORT = { project: "项", space: "空" };
const TYPE_CLASS = { 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, project: 3, space: 4 };

const dim = ref("org");
const treeLoading = ref(false);
const loading = ref(false);
const summary = reactive({ count: 0, orig_value: 0, net_value: 0, high_value: 0 });
const tree = ref([]);
const selected = ref(null);
const sel = computed(() => selected.value || {});

const rows = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const q = reactive({ keyword: "", status: null });

function nodeTypeShort(data) {
  if (data.node_type === "space") return "空";
  return dim.value === "org" ? TYPE_SHORT[data.org_type] || "" : SPACE_SHORT[data.node_type] || "";
}
function nodeTypeClass(data) {
  if (data.node_type === "space") return "tnode__type--4";
  return `tnode__type--${TYPE_CLASS[dim.value === "org" ? data.org_type : data.node_type] || 1}`;
}

async function loadTree() {
  treeLoading.value = true;
  try {
    const res = dim.value === "org" ? await assetApi.statsTree() : await assetApi.statsSpaceTree();
    Object.assign(summary, res.summary);
    tree.value = res.tree;
  } finally {
    treeLoading.value = false;
  }
}

async function loadDetail() {
  loading.value = true;
  try {
    const params = { page: page.value, page_size: pageSize.value };
    if (selected.value) {
      if (selected.value.node_type === "space") params.space_id = selected.value.id;
      else if (dim.value === "org") params.node_id = selected.value.id;
      else if (selected.value.node_type === "project") params.space_project_id = selected.value.id;
      else params.space_id = selected.value.id;
    }
    if (q.keyword.trim()) params.keyword = q.keyword.trim();
    if (q.status != null && q.status !== "") params.status = q.status;
    const res = await assetApi.statsDetail(params);
    rows.value = res.records;
    total.value = res.total;
  } finally {
    loading.value = false;
  }
}

function onDimChange() {
  selected.value = null;
  page.value = 1;
  loadTree().then(loadDetail);
}

function onNodeClick(data) {
  selected.value = data;
  page.value = 1;
  loadDetail();
}

function clearNode() {
  selected.value = null;
  page.value = 1;
  loadDetail();
}

function search() {
  page.value = 1;
  loadDetail();
}

onMounted(async () => {
  await loadTree();
  await loadDetail();
});
</script>

<style scoped>
.kpis {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  flex-shrink: 0;
}
.kpi { padding: 14px 18px; }
.kpi__label { color: var(--ink-2); font-size: 12px; letter-spacing: 1px; }
.kpi__value {
  font-family: var(--serif);
  font-size: 26px;
  font-weight: 700;
  color: var(--navy);
  margin: 6px 0 4px;
  font-variant-numeric: tabular-nums;
}
.kpi__foot { font-size: 12px; color: var(--ink-3); }

.body {
  flex: 1;
  min-height: 0;
  display: flex;
  gap: 14px;
}

/* ---------- 左侧组织树 ---------- */
.tree-card {
  width: 300px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.tree-card__dims {
  padding: 10px 12px 0;
}
.tree-card__title {
  padding: 12px 16px 8px;
  font-weight: 600;
  color: var(--navy);
  font-size: 13px;
  border-bottom: 1px solid var(--line);
}
.tree-card__all {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 9px 16px;
  font-size: 13px;
  cursor: pointer;
  border-bottom: 1px solid var(--line);
}
.tree-card__all:hover { background: #faf6ec; }
.tree-card__all.on {
  background: linear-gradient(90deg, rgba(176, 122, 46, 0.14), rgba(176, 122, 46, 0.04));
  font-weight: 600;
  color: var(--navy);
}
.tree-card__scroll { flex: 1; }

.tnode {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding-right: 6px;
  gap: 8px;
}
.tnode__name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tnode__type {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 3px;
  font-size: 11px;
  margin-right: 6px;
  flex-shrink: 0;
}
.tnode__type--1 { background: rgba(29, 61, 92, 0.12); color: var(--navy); }
.tnode__type--2 { background: rgba(42, 109, 160, 0.12); color: #2a6da0; }
.tnode__type--3 { background: rgba(46, 125, 79, 0.12); color: #2e7d4f; }
.tnode__type--4 { background: rgba(176, 122, 46, 0.14); color: var(--gold-deep); }
.tnode__type--5 { background: #eef1f4; color: #8a99a8; }
.tnode__meta { color: var(--ink-3); font-size: 11px; white-space: nowrap; flex-shrink: 0; }
:deep(.el-tree-node.is-current > .el-tree-node__content) {
  background: linear-gradient(90deg, rgba(176, 122, 46, 0.2), rgba(176, 122, 46, 0.05)) !important;
}

/* ---------- 右侧明细 ---------- */
.detail-card {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.detail-scope {
  font-size: 13px;
  color: var(--navy);
  font-weight: 600;
}
.flex-table { flex: 1; min-height: 0; }
.code-link { color: var(--brand); text-decoration: none; cursor: pointer; }
.code-link:hover { text-decoration: underline; }
</style>
