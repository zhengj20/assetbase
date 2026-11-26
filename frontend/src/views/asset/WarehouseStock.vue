<template>
  <div class="page">
    <div class="page__head">
      <h1 class="page__title">仓库库存</h1>
      <span class="page__sub">在库口径：绑定仓库且状态为「在库」 · 点击统计行可下钻库存查询</span>
    </div>

    <!-- 顶部汇总 -->
    <div class="kpis">
      <div class="card kpi">
        <div class="kpi__label">有库存仓库</div>
        <div class="kpi__value num">{{ s.warehouses.length }}</div>
        <div class="kpi__foot">启用仓库共 {{ s.warehouse_count }} 个</div>
      </div>
      <div class="card kpi">
        <div class="kpi__label">在库资产</div>
        <div class="kpi__value num">{{ s.in_stock_count }}</div>
        <div class="kpi__foot">高值在库 {{ s.high_value }} 项</div>
      </div>
      <div class="card kpi">
        <div class="kpi__label">在库原值</div>
        <div class="kpi__value num"><span class="money">{{ fmtMoney(s.in_stock_price) }}</span></div>
        <div class="kpi__foot">在库资产成本合计</div>
      </div>
      <div class="card kpi">
        <div class="kpi__label">在库净值</div>
        <div class="kpi__value num"><span class="money">{{ fmtMoney(s.in_stock_net) }}</span></div>
        <div class="kpi__foot">扣累计折旧后</div>
      </div>
    </div>

    <!-- 统计：仓库维度 + 分类维度 -->
    <div class="stats-row">
      <div class="card stats-card">
        <div class="stats-card__title">仓库库存统计</div>
        <el-table :data="s.warehouses" v-loading="statsLoading" size="small" max-height="170"
          @row-click="(row) => drill({ warehouse_id: row.warehouse_id, category_id: null })">
          <el-table-column prop="warehouse_name" label="仓库" min-width="140" show-overflow-tooltip />
          <el-table-column prop="in_stock_count" label="在库数量" width="90" align="right">
            <template #default="{ row }"><span class="num">{{ row.in_stock_count }}</span></template>
          </el-table-column>
          <el-table-column label="在库原值" width="120" align="right">
            <template #default="{ row }"><span class="money">{{ fmtMoney(row.in_stock_price) }}</span></template>
          </el-table-column>
          <el-table-column label="在库净值" width="120" align="right">
            <template #default="{ row }"><span class="num">{{ fmtMoney(row.in_stock_net) }}</span></template>
          </el-table-column>
          <el-table-column prop="high_value" label="高值" width="64" align="right">
            <template #default="{ row }"><span class="num">{{ row.high_value }}</span></template>
          </el-table-column>
        </el-table>
        <div v-if="!statsLoading && !s.warehouses.length" class="empty-hint">暂无在库资产</div>
      </div>

      <div class="card stats-card">
        <div class="stats-card__title">分类库存统计</div>
        <el-table :data="s.categories" v-loading="statsLoading" size="small" max-height="170"
          @row-click="(row) => row.category_id && drill({ warehouse_id: null, category_id: row.category_id })">
          <el-table-column prop="category_name" label="资产分类" min-width="140" show-overflow-tooltip />
          <el-table-column prop="in_stock_count" label="在库数量" width="90" align="right">
            <template #default="{ row }"><span class="num">{{ row.in_stock_count }}</span></template>
          </el-table-column>
          <el-table-column label="在库原值" width="120" align="right">
            <template #default="{ row }"><span class="money">{{ fmtMoney(row.in_stock_price) }}</span></template>
          </el-table-column>
          <el-table-column label="在库净值" width="120" align="right">
            <template #default="{ row }"><span class="num">{{ fmtMoney(row.in_stock_net) }}</span></template>
          </el-table-column>
        </el-table>
        <div v-if="!statsLoading && !s.categories.length" class="empty-hint">暂无在库资产</div>
      </div>
    </div>

    <!-- 库存查询 -->
    <div class="card table-card">
      <div class="filter-bar">
        <el-select v-model="q.warehouse_id" placeholder="仓库" clearable filterable @change="reload">
          <el-option v-for="w in warehouses" :key="w.id" :label="w.warehouse_name" :value="w.id" />
        </el-select>
        <el-select v-model="q.category_id" placeholder="资产分类" clearable filterable @change="reload">
          <el-option v-for="c in categories" :key="c.id" :label="c.category_name" :value="c.id" />
        </el-select>
        <el-select v-model="q.status" placeholder="状态" clearable style="width: 130px" @change="reload">
          <el-option v-for="st in ASSET_STATUS" :key="st.value" :label="st.label" :value="st.value" />
        </el-select>
        <el-input v-model="q.keyword" placeholder="编码/名称/规格" clearable style="width: 180px" @keyup.enter="reload" />
        <el-button type="primary" plain @click="reload">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" height="100%" class="flex-table">
        <el-table-column prop="asset_code" label="资产编码" width="170">
          <template #default="{ row }">
            <router-link class="code-link num" :to="`/asset/list?focus=${row.id}`">{{ row.asset_code }}</router-link>
          </template>
        </el-table-column>
        <el-table-column prop="asset_name" label="资产名称" min-width="170" show-overflow-tooltip />
        <el-table-column prop="category_name" label="分类" width="110" />
        <el-table-column prop="spec" label="规格" min-width="140" show-overflow-tooltip />
        <el-table-column label="状态" width="86" align="center">
          <template #default="{ row }"><span class="st" :class="`st--${row.status}`">{{ assetStatusName(row.status) }}</span></template>
        </el-table-column>
        <el-table-column label="原值" width="110" align="right">
          <template #default="{ row }"><span class="money">{{ fmtMoney(row.price) }}</span></template>
        </el-table-column>
        <el-table-column label="净值" width="110" align="right">
          <template #default="{ row }"><span class="num">{{ fmtMoney(row.net_value) }}</span></template>
        </el-table-column>
        <el-table-column prop="warehouse_name" label="仓库" width="140" show-overflow-tooltip />
        <el-table-column label="建档时间" width="106" align="center">
          <template #default="{ row }">{{ fmtDate(row.create_time) }}</template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <span class="text-muted">共 {{ total }} 项</span>
        <el-pagination
          v-model:current-page="page" v-model:page-size="pageSize" :total="total"
          :page-sizes="[20, 50]" layout="sizes, prev, pager, next" background
          @current-change="load" @size-change="() => { page = 1; load(); }"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { assetApi, archiveApi } from "../../api";
import { ASSET_STATUS, assetStatusName, fmtMoney, fmtDate } from "../../utils/constants";

const statsLoading = ref(false);
const loading = ref(false);
const s = reactive({
  warehouse_count: 0, in_stock_count: 0, in_stock_price: 0, in_stock_net: 0, high_value: 0,
  warehouses: [], categories: [],
});
const warehouses = ref([]);
const categories = ref([]);
const rows = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const q = reactive({ warehouse_id: null, category_id: null, status: 1, keyword: "" });

async function loadStats() {
  statsLoading.value = true;
  try {
    const res = await assetApi.warehouseStock();
    Object.assign(s, res.summary, { warehouses: res.warehouses, categories: res.categories });
  } finally {
    statsLoading.value = false;
  }
}

async function load() {
  loading.value = true;
  try {
    const params = { page: page.value, page_size: pageSize.value };
    if (q.warehouse_id) params.warehouse_id = q.warehouse_id;
    if (q.category_id) params.category_id = q.category_id;
    if (q.status != null && q.status !== "") params.status = q.status;
    if (q.keyword.trim()) params.keyword = q.keyword.trim();
    const res = await assetApi.list(params);
    rows.value = res.records;
    total.value = res.total;
  } finally {
    loading.value = false;
  }
}

function reload() {
  page.value = 1;
  load();
}

function reset() {
  q.warehouse_id = null;
  q.category_id = null;
  q.status = 1;
  q.keyword = "";
  page.value = 1;
  load();
}

/** 统计行下钻：带筛选条件刷新下方查询（「未分类」行无分类 id，不可下钻） */
function drill(conds) {
  Object.assign(q, { ...conds, keyword: "" });
  reload();
}

onMounted(async () => {
  try {
    const [ws, cats] = await Promise.all([archiveApi.warehouses(), archiveApi.categories()]);
    warehouses.value = Array.isArray(ws) ? ws : ws.records || [];
    categories.value = Array.isArray(cats) ? cats : [];
  } catch {
    warehouses.value = [];
    categories.value = [];
  }
  loadStats();
  load();
});
</script>

<style scoped>
.kpis {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  flex-shrink: 0;
}
.kpi { padding: 10px 14px; }
.kpi__label { color: var(--ink-2); font-size: 11px; letter-spacing: 1px; }
.kpi__value {
  font-family: var(--serif);
  font-size: 20px;
  font-weight: 700;
  color: var(--navy);
  margin: 3px 0 2px;
  font-variant-numeric: tabular-nums;
}
.kpi__foot { font-size: 11px; color: var(--ink-3); }

.stats-row {
  display: flex;
  gap: 14px;
  flex-shrink: 0;
}
.stats-card {
  flex: 1;
  min-width: 0;
  overflow: hidden;
}
.stats-card__title {
  padding: 8px 16px 6px;
  font-weight: 600;
  color: var(--navy);
  font-size: 13px;
  border-bottom: 1px solid var(--line);
}
.stats-card :deep(.el-table__row) { cursor: pointer; }

.table-card { flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
.flex-table { flex: 1; min-height: 0; }
.code-link { color: var(--brand); text-decoration: none; cursor: pointer; }
.code-link:hover { text-decoration: underline; }
</style>
