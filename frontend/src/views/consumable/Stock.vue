<template>
  <div class="page">
    <div class="page__head">
      <h1 class="page__title">易耗品库存</h1>
      <span class="page__sub">实时库存余额 · 入库增加 / 领用减少 · 在库口径：数量大于 0 · 点击统计行可下钻库存查询</span>
    </div>

    <!-- 顶部汇总 -->
    <div class="kpis">
      <div class="card kpi">
        <div class="kpi__label">有库存仓库</div>
        <div class="kpi__value num">{{ s.warehouses.length }}</div>
        <div class="kpi__foot">启用仓库共 {{ s.warehouse_count }} 个</div>
      </div>
      <div class="card kpi">
        <div class="kpi__label">在库记录</div>
        <div class="kpi__value num">{{ s.stock_records }}</div>
        <div class="kpi__foot">断货 {{ s.stockout_count }} 项</div>
      </div>
      <div class="card kpi">
        <div class="kpi__label">库存总量</div>
        <div class="kpi__value num">{{ s.total_qty }}</div>
        <div class="kpi__foot">各仓库数量合计</div>
      </div>
      <div class="card kpi">
        <div class="kpi__label">库存金额</div>
        <div class="kpi__value num"><span class="money">{{ fmtMoney(s.total_amount) }}</span></div>
        <div class="kpi__foot">按成本单价计</div>
      </div>
    </div>

    <!-- 统计：仓库维度 + 分类维度 -->
    <div class="stats-row">
      <div class="card stats-card">
        <div class="stats-card__title">仓库库存统计</div>
        <el-table :data="s.warehouses" v-loading="statsLoading" size="small" max-height="170"
          @row-click="(row) => drill({ warehouse_id: row.warehouse_id, category: '' })">
          <el-table-column prop="warehouse_name" label="仓库" min-width="140" show-overflow-tooltip />
          <el-table-column prop="stock_records" label="在库记录" width="90" align="right">
            <template #default="{ row }"><span class="num">{{ row.stock_records }}</span></template>
          </el-table-column>
          <el-table-column prop="total_qty" label="总数量" width="100" align="right">
            <template #default="{ row }"><span class="num">{{ row.total_qty }}</span></template>
          </el-table-column>
          <el-table-column label="库存金额" width="120" align="right">
            <template #default="{ row }"><span class="money">{{ fmtMoney(row.total_amount) }}</span></template>
          </el-table-column>
        </el-table>
        <div v-if="!statsLoading && !s.warehouses.length" class="empty-hint">暂无在库物料</div>
      </div>

      <div class="card stats-card">
        <div class="stats-card__title">分类库存统计</div>
        <el-table :data="s.categories" v-loading="statsLoading" size="small" max-height="170"
          @row-click="(row) => row.category !== '未分类' && drill({ warehouse_id: null, category: row.category })">
          <el-table-column prop="category" label="分类" min-width="140" show-overflow-tooltip />
          <el-table-column prop="stock_records" label="在库记录" width="90" align="right">
            <template #default="{ row }"><span class="num">{{ row.stock_records }}</span></template>
          </el-table-column>
          <el-table-column prop="total_qty" label="总数量" width="100" align="right">
            <template #default="{ row }"><span class="num">{{ row.total_qty }}</span></template>
          </el-table-column>
          <el-table-column label="库存金额" width="120" align="right">
            <template #default="{ row }"><span class="money">{{ fmtMoney(row.total_amount) }}</span></template>
          </el-table-column>
        </el-table>
        <div v-if="!statsLoading && !s.categories.length" class="empty-hint">暂无在库物料</div>
      </div>
    </div>

    <!-- 库存查询 -->
    <div class="card table-card">
      <div class="filter-bar">
        <el-input v-model="q.keyword" placeholder="物料编码/名称" clearable :prefix-icon="Search" @keyup.enter="reload" />
        <el-select v-model="q.warehouse_id" placeholder="仓库" clearable filterable style="width: 180px" @change="reload">
          <el-option v-for="w in warehouses" :key="w.id" :label="w.warehouse_name" :value="w.id" />
        </el-select>
        <el-select v-model="q.category" placeholder="分类" clearable filterable style="width: 150px" @change="reload">
          <el-option v-for="c in s.categories" :key="c.category" :label="c.category" :value="c.category" />
        </el-select>
        <el-button type="primary" plain @click="reload">查询</el-button>
        <el-button @click="reset">重置</el-button>
        <el-button v-if="q.warehouse_id" plain :icon="Delete" style="margin-left: auto" @click="q.warehouse_id = null; reload()">清除仓库</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" height="100%" class="flex-table">
        <el-table-column prop="item_code" label="物料编码" width="120" fixed />
        <el-table-column prop="item_name" label="物料名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="category" label="分类" width="110" show-overflow-tooltip />
        <el-table-column prop="item_unit" label="单位" width="70" align="center" />
        <el-table-column prop="warehouse_name" label="仓库" width="140" show-overflow-tooltip />
        <el-table-column label="现有数量" width="110" align="right">
          <template #default="{ row }"><span class="num" :class="{ 'low': row.qty <= 0 }">{{ row.qty }}</span></template>
        </el-table-column>
        <el-table-column label="成本单价" width="110" align="right">
          <template #default="{ row }"><span class="num">{{ fmtMoney(row.unit_price) }}</span></template>
        </el-table-column>
        <el-table-column label="库存金额" min-width="120" align="right">
          <template #default="{ row }"><span class="num">{{ fmtMoney((row.qty || 0) * (row.unit_price || 0)) }}</span></template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <span class="text-muted">共 {{ total }} 条库存记录</span>
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
import { Search, Delete } from "@element-plus/icons-vue";
import { conApi, archiveApi } from "../../api";
import { fmtMoney } from "../../utils/constants";

const statsLoading = ref(false);
const loading = ref(false);
const s = reactive({
  warehouse_count: 0, stock_records: 0, total_qty: 0, total_amount: 0, stockout_count: 0,
  warehouses: [], categories: [],
});
const rows = ref([]);
const warehouses = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const q = reactive({ keyword: "", warehouse_id: null, category: "" });

async function loadStats() {
  statsLoading.value = true;
  try {
    const res = await conApi.stockSummary();
    Object.assign(s, res.summary, { warehouses: res.warehouses, categories: res.categories });
  } finally {
    statsLoading.value = false;
  }
}

async function load() {
  loading.value = true;
  try {
    const params = { page: page.value, page_size: pageSize.value };
    if (q.keyword) params.keyword = q.keyword;
    if (q.warehouse_id) params.warehouse_id = q.warehouse_id;
    if (q.category) params.category = q.category;
    const res = await conApi.stock(params);
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
  q.keyword = "";
  q.warehouse_id = null;
  q.category = "";
  page.value = 1;
  load();
}

/** 统计行下钻：带筛选条件刷新下方查询（「未分类」行无分类值，不可下钻） */
function drill(conds) {
  Object.assign(q, { ...conds, keyword: "" });
  reload();
}

onMounted(async () => {
  try {
    const ws = await archiveApi.warehouses();
    warehouses.value = Array.isArray(ws) ? ws : ws.records || [];
  } catch {
    warehouses.value = [];
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
.low { color: #f56c6c; font-weight: 600; }
</style>
