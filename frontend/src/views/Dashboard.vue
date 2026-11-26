<template>
  <div class="page" v-loading="loading">
    <div class="page__head">
      <h1 class="page__title">资产驾驶舱</h1>
      <span class="page__sub">按数据权限实时汇总 · {{ user?.real_name }}，{{ today }}</span>
    </div>

    <!-- 核心指标卡 -->
    <div class="kpis">
      <div class="card kpi">
        <div class="kpi__label">资产总数</div>
        <div class="kpi__value num">{{ d.cards.total }}</div>
        <div class="kpi__foot">在库 {{ d.cards.in_stock }} · 领用中 {{ d.cards.in_use }}</div>
      </div>
      <div class="card kpi">
        <div class="kpi__label">资产原值</div>
        <div class="kpi__value num">¥{{ fmtMoney(d.cards.orig_value) }}</div>
        <div class="kpi__foot">净值 ¥{{ fmtMoney(d.cards.net_value) }}</div>
      </div>
      <div class="card kpi">
        <div class="kpi__label">本月新增 / 报废</div>
        <div class="kpi__value num">
          <span class="up">+{{ d.cards.new_month }}</span>
          <span class="kpi__sep">/</span>
          <span class="down">-{{ d.cards.scrap_month }}</span>
        </div>
        <div class="kpi__foot">在途调拨 {{ d.cards.in_transfer }} 项</div>
      </div>
      <div class="card kpi">
        <div class="kpi__label">待办审批</div>
        <div class="kpi__value num" :class="{ 'kpi__value--warn': d.cards.todo_count > 0 }">
          {{ d.cards.todo_count }}
        </div>
        <div class="kpi__foot"><router-link to="/doc/approval">前往处理 →</router-link></div>
      </div>
    </div>

    <!-- 易耗品指标卡 -->
    <div class="kpis">
      <div class="card kpi">
        <div class="kpi__label">易耗品库存金额</div>
        <div class="kpi__value num">¥{{ fmtMoney(d.con_metrics.stock_value) }}</div>
        <div class="kpi__foot">{{ d.con_metrics.sku_count }} 种物料在库</div>
      </div>
      <div class="card kpi">
        <div class="kpi__label">本月领用</div>
        <div class="kpi__value num">¥{{ fmtMoney(d.con_metrics.issue_month_amount) }}</div>
        <div class="kpi__foot">{{ d.con_metrics.issue_month_num }} 张领用单</div>
      </div>
      <div class="card kpi">
        <div class="kpi__label">本月采购</div>
        <div class="kpi__value num">¥{{ fmtMoney(d.con_metrics.purchase_month_amount) }}</div>
        <div class="kpi__foot">已生效采购单金额</div>
      </div>
      <div class="card kpi">
        <div class="kpi__label">断货物料</div>
        <div class="kpi__value num" :class="{ 'kpi__value--warn': d.con_metrics.stockout_count > 0 }">
          {{ d.con_metrics.stockout_count }}
        </div>
        <div class="kpi__foot"><router-link to="/con/stock">前往补货 →</router-link></div>
      </div>
    </div>

    <!-- 快捷入口（方案模块2：高频业务一键直达） -->
    <div class="quick">
      <router-link class="quick__item" to="/doc/purchase"><el-icon><ShoppingCart /></el-icon><span>采购申请</span></router-link>
      <router-link class="quick__item" to="/doc/stock-in"><el-icon><Download /></el-icon><span>资产入库</span></router-link>
      <router-link class="quick__item" to="/check/task"><el-icon><Tickets /></el-icon><span>盘点任务</span></router-link>
      <router-link class="quick__item" to="/asset/list"><el-icon><Search /></el-icon><span>资产查询</span></router-link>
    </div>

    <!-- 地产行业特色指标 -->
    <div class="estate">
      <div class="estate__item">
        <span>样板间资产闲置率</span><b class="num">{{ pct(d.estate_metrics.sample_idle_ratio) }}</b>
      </div>
      <div class="estate__item">
        <span>呆滞资产</span><b class="num">{{ d.estate_metrics.stale_count }} 项（{{ pct(d.estate_metrics.stale_ratio) }}）</b>
      </div>
      <div class="estate__item">
        <span>清盘待处置</span><b class="num">{{ d.estate_metrics.clearing_pending }} 项</b>
      </div>
      <div class="estate__item">
        <span>资产复用率</span><b class="num">{{ pct(d.estate_metrics.reusable_ratio) }}</b>
      </div>
    </div>

    <!-- 预警条 -->
    <div v-if="d.alerts.length" class="alerts card">
      <div v-for="(a, i) in d.alerts" :key="i" class="alert" :class="`alert--${a.level}`">
        <el-icon><BellFilled /></el-icon>{{ a.message }}
      </div>
    </div>

    <!-- 图表区 -->
    <div class="charts">
      <div class="card chart-card">
        <div class="sec-title">公司/项目维度资产价值分布</div>
        <div ref="pieRef" class="chart chart--pie"></div>
      </div>
      <div class="card chart-card">
        <div class="sec-title">近 6 个月资产新增趋势</div>
        <div ref="trendRef" class="chart"></div>
      </div>
      <div class="card chart-card">
        <div class="sec-title">近 6 个月易耗品领用金额</div>
        <div ref="conTrendRef" class="chart"></div>
      </div>
      <div class="card chart-card">
        <div class="sec-title">易耗品领用 Top10（近 6 个月）</div>
        <div ref="conTopRef" class="chart"></div>
      </div>
      <div class="card chart-card chart-card--wide">
        <div class="sec-title">资产分类数量统计</div>
        <div ref="barRef" class="chart"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, reactive, ref, nextTick } from "vue";
import * as echarts from "echarts";
import { dashboardApi } from "../api";
import { useAuthStore } from "../stores/auth";
import { fmtMoney, pct } from "../utils/constants";

const auth = useAuthStore();
const user = computed(() => auth.user);
const today = new Date().toLocaleDateString("zh-CN", { year: "numeric", month: "long", day: "numeric" });

const loading = ref(false);
const d = reactive({
  cards: { total: 0, orig_value: 0, net_value: 0, in_stock: 0, in_use: 0, in_transfer: 0, new_month: 0, scrap_month: 0, todo_count: 0 },
  estate_metrics: {},
  con_metrics: { stock_value: 0, sku_count: 0, issue_month_num: 0, issue_month_amount: 0, purchase_month_amount: 0, stockout_count: 0 },
  org_distribution: [],
  category_distribution: [],
  trend: [],
  con_top_items: [],
  alerts: [],
});

const pieRef = ref();
const trendRef = ref();
const conTrendRef = ref();
const conTopRef = ref();
const barRef = ref();

// 图表实例与 resize 监听器需组件级保存，卸载时释放（避免重复初始化/内存泄漏）
let charts = [];
let onResize = null;

onMounted(async () => {
  loading.value = true;
  try {
    const res = await dashboardApi.get();
    Object.assign(d, res);
    await nextTick();
    renderCharts();
  } finally {
    loading.value = false;
  }
});

const NAVY = "#1d3d5c";
const GOLD = "#b07a2e";

function renderCharts() {
  // 饼图：公司维度价值分布
  const pie = echarts.init(pieRef.value);
  pie.setOption({
    tooltip: { trigger: "item", formatter: "{b}<br/>{c} 项（{d}%）" },
    series: [
      {
        type: "pie",
        radius: ["42%", "70%"],
        center: ["50%", "50%"],
        itemStyle: { borderColor: "#fff", borderWidth: 2 },
        label: { formatter: "{b}\n{c} 项", fontSize: 11, color: "#5b6b7a" },
        data: d.org_distribution.map((r) => ({ name: r.name, value: r.count })),
      },
    ],
    color: [NAVY, GOLD, "#2a6da0", "#8f6222", "#5b87a5", "#c8a05a", "#93a1ad"],
  });

  // 折线：新增趋势
  const trend = echarts.init(trendRef.value);
  trend.setOption({
    grid: { left: 40, right: 16, top: 20, bottom: 26 },
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: d.trend.map((t) => t.month), axisLine: { lineStyle: { color: "#e7e3d9" } } },
    yAxis: { type: "value", minInterval: 1, splitLine: { lineStyle: { color: "#f0ede5" } } },
    series: [
      {
        type: "line",
        data: d.trend.map((t) => t.added),
        smooth: true,
        symbol: "circle",
        symbolSize: 7,
        lineStyle: { width: 2.5, color: NAVY },
        itemStyle: { color: NAVY, borderColor: GOLD, borderWidth: 2 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "rgba(29, 61, 92, 0.18)" },
            { offset: 1, color: "rgba(29, 61, 92, 0.01)" },
          ]),
        },
      },
    ],
  });

  // 折线：易耗品领用金额趋势
  const conTrend = echarts.init(conTrendRef.value);
  conTrend.setOption({
    grid: { left: 56, right: 16, top: 20, bottom: 26 },
    tooltip: { trigger: "axis", valueFormatter: (v) => `¥${fmtMoney(v)}` },
    xAxis: { type: "category", data: d.trend.map((t) => t.month), axisLine: { lineStyle: { color: "#e7e3d9" } } },
    yAxis: { type: "value", splitLine: { lineStyle: { color: "#f0ede5" } } },
    series: [
      {
        type: "line",
        data: d.trend.map((t) => t.con_amount ?? 0),
        smooth: true,
        symbol: "circle",
        symbolSize: 7,
        lineStyle: { width: 2.5, color: GOLD },
        itemStyle: { color: GOLD, borderColor: "#fff", borderWidth: 2 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "rgba(176, 122, 46, 0.18)" },
            { offset: 1, color: "rgba(176, 122, 46, 0.01)" },
          ]),
        },
      },
    ],
  });

  // 条形：易耗品领用 Top10（横向，金额降序置顶）
  const conTop = echarts.init(conTopRef.value);
  const topItems = [...d.con_top_items].reverse();
  conTop.setOption({
    grid: { left: 8, right: 64, top: 12, bottom: 12, containLabel: true },
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, valueFormatter: (v) => `¥${fmtMoney(v)}` },
    xAxis: { type: "value", splitLine: { lineStyle: { color: "#f0ede5" } } },
    yAxis: {
      type: "category",
      data: topItems.map((t) => t.name),
      axisLine: { lineStyle: { color: "#e7e3d9" } },
      axisLabel: { color: "#5b6b7a" },
    },
    series: [
      {
        type: "bar",
        data: topItems.map((t) => t.amount),
        barMaxWidth: 16,
        itemStyle: { color: NAVY, borderRadius: [0, 3, 3, 0] },
        label: { show: true, position: "right", formatter: (p) => fmtMoney(p.value), fontSize: 11, color: "#5b6b7a" },
      },
    ],
  });

  // 柱图：分类统计
  const bar = echarts.init(barRef.value);
  bar.setOption({
    grid: { left: 40, right: 16, top: 20, bottom: 26 },
    tooltip: { trigger: "axis" },
    xAxis: {
      type: "category",
      data: d.category_distribution.map((c) => c.name),
      axisLine: { lineStyle: { color: "#e7e3d9" } },
      axisLabel: { interval: 0, color: "#5b6b7a" },
    },
    yAxis: { type: "value", minInterval: 1, splitLine: { lineStyle: { color: "#f0ede5" } } },
    series: [
      {
        type: "bar",
        data: d.category_distribution.map((c) => c.count),
        barMaxWidth: 34,
        itemStyle: { color: GOLD, borderRadius: [3, 3, 0, 0] },
      },
    ],
  });

  onResize = () => {
    charts.forEach((c) => c.resize());
  };
  window.addEventListener("resize", onResize);
  charts = [pie, trend, conTrend, conTop, bar];
}

onBeforeUnmount(() => {
  if (onResize) window.removeEventListener("resize", onResize);
  charts.forEach((c) => c.dispose());
  charts = [];
  onResize = null;
});
</script>

<style scoped>
/* 驾驶舱为固定高度内容，允许整页纵向滚动（覆盖全局 .page 的 overflow:hidden） */
.page {
  overflow-y: auto;
  overflow-x: hidden;
}
.kpis {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  flex-shrink: 0;
}
.kpi { padding: 16px 20px; }
.kpi__label { color: var(--ink-2); font-size: 12px; letter-spacing: 1px; }
.kpi__value {
  font-family: var(--serif);
  font-size: 30px;
  font-weight: 700;
  color: var(--navy);
  margin: 8px 0 4px;
  font-variant-numeric: tabular-nums;
}
.kpi__value--warn { color: var(--danger); }
.kpi__value .up { color: var(--ok); }
.kpi__value .down { color: var(--danger); }
.kpi__sep { color: var(--ink-3); margin: 0 8px; font-weight: 400; }
.kpi__foot { font-size: 12px; color: var(--ink-3); }
.kpi__foot a { color: var(--brand); }

.quick {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  flex-shrink: 0;
}
.quick__item {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 0;
  background: #fff;
  border: 1px solid var(--line, #e7e3d9);
  border-radius: var(--radius, 8px);
  font-size: 13px;
  color: var(--ink, #2b3945);
  text-decoration: none;
  transition: all 0.15s;
}
.quick__item :deep(.el-icon) { font-size: 18px; color: var(--navy); }
.quick__item:hover {
  border-color: var(--brand, #b07a2e);
  box-shadow: 0 2px 10px rgba(176, 122, 46, 0.18);
  transform: translateY(-1px);
}

.estate {
  display: flex;
  gap: 14px;
  flex-shrink: 0;
}
.estate__item {
  flex: 1;
  background: linear-gradient(135deg, #fbf8f1, #f6efe0);
  border: 1px solid var(--gold-line);
  border-radius: var(--radius);
  padding: 10px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: var(--gold-deep);
}
.estate__item b { font-size: 14px; color: var(--navy); font-variant-numeric: tabular-nums; }

.alerts { padding: 10px 16px; display: flex; flex-direction: column; gap: 6px; flex-shrink: 0; }
.alert { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.alert--warning { color: var(--warn); }
.alert--danger { color: var(--danger); }
.alert--info { color: var(--brand); }

.charts {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  flex: 1;
  min-height: 0;
}
.chart-card { padding: 16px 18px; display: flex; flex-direction: column; }
.chart-card--wide { grid-column: 1 / -1; }
.chart { flex: 1; min-height: 200px; }
.chart--pie { min-height: 240px; }
</style>
