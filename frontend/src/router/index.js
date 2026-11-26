import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "../stores/auth";

const routes = [
  { path: "/login", name: "login", component: () => import("../views/Login.vue"), meta: { title: "登录" } },
  { path: "/m/stocktake", component: () => import("../views/mobile/Stocktake.vue"), meta: { title: "移动端盘点" } },
  { path: "/m/approval", component: () => import("../views/mobile/Approval.vue"), meta: { title: "移动端审批" } },
  {
    path: "/",
    component: () => import("../layout/MainLayout.vue"),
    redirect: "/dashboard",
    children: [
      { path: "workbench", component: () => import("../views/Workbench.vue"), meta: { title: "工作台" } },
      { path: "dashboard", component: () => import("../views/Dashboard.vue"), meta: { title: "驾驶舱" } },
      { path: "asset/list", component: () => import("../views/asset/AssetList.vue"), meta: { title: "资产台账", perm: "asset:list" } },
      { path: "asset/warehouse-stock", component: () => import("../views/asset/WarehouseStock.vue"), meta: { title: "仓库库存", perm: "warehouse_stock:list" } },
      { path: "asset/stats", component: () => import("../views/asset/AssetStats.vue"), meta: { title: "资产统计", perm: "asset:stats" } },
      { path: "asset/depreciation", component: () => import("../views/asset/Depreciation.vue"), meta: { title: "折旧管理", perm: "depreciation:list" } },
      { path: "asset/group", component: () => import("../views/asset/GroupList.vue"), meta: { title: "组合包", perm: "group:list" } },
      { path: "messages", component: () => import("../views/system/Messages.vue"), meta: { title: "消息中心", perm: "message:list" } },
      { path: "search", component: () => import("../views/Search.vue"), meta: { title: "全局搜索", perm: "asset:search" } },
      { path: "doc/purchase", component: () => import("../views/doc/Purchase.vue"), meta: { title: "采购申请", perm: "purchase:list" } },
      { path: "doc/stock-in", component: () => import("../views/doc/StockIn.vue"), meta: { title: "入库管理", perm: "stockin:list" } },
      { path: "doc/stock-out", component: () => import("../views/doc/StockOut.vue"), meta: { title: "出库管理", perm: "stockout:list" } },
      { path: "doc/transfer", component: () => import("../views/doc/Transfer.vue"), meta: { title: "调拨管理", perm: "transfer:list" } },
      { path: "doc/borrow", component: () => import("../views/doc/Borrow.vue"), meta: { title: "借用管理", perm: "borrow:list" } },
      { path: "doc/return", component: () => import("../views/doc/Return.vue"), meta: { title: "归还管理", perm: "return:list" } },
      { path: "doc/scrap", component: () => import("../views/doc/Scrap.vue"), meta: { title: "报废处置", perm: "scrap:list" } },
      { path: "doc/approval", component: () => import("../views/doc/Approval.vue"), meta: { title: "我的审批", perm: "approval:list" } },
      { path: "doc/progress/:instanceId", component: () => import("../views/doc/ApprovalProgress.vue"), meta: { title: "审批进度" } },
      { path: "doc/detail/:bizType/:id", component: () => import("../views/doc/DocumentDetail.vue"), meta: { title: "单据详情" } },
      { path: "doc/flow", component: () => import("../views/doc/FlowConfig.vue"), meta: { title: "流程配置", perm: "flow:config" } },
      { path: "con/item", component: () => import("../views/consumable/Item.vue"), meta: { title: "物料档案", perm: "con_item:list" } },
      { path: "con/purchase", component: () => import("../views/consumable/Purchase.vue"), meta: { title: "采购管理", perm: "con_purchase:list" } },
      { path: "con/inbound", component: () => import("../views/consumable/Inbound.vue"), meta: { title: "易耗入库", perm: "con_inbound:list" } },
      { path: "con/issue", component: () => import("../views/consumable/Issue.vue"), meta: { title: "领用管理", perm: "con_issue:list" } },
      { path: "con/stock", component: () => import("../views/consumable/Stock.vue"), meta: { title: "库存查询", perm: "con_stock:list" } },
      { path: "approval/monitor", component: () => import("../views/approval/FlowMonitor.vue"), meta: { title: "流程监控", perm: "approval:monitor" } },
      { path: "check/task", component: () => import("../views/check/CheckTask.vue"), meta: { title: "盘点任务", perm: "check:list" } },
      { path: "archive/category", component: () => import("../views/archive/Category.vue"), meta: { title: "资产分类", perm: "category:list" } },
      { path: "archive/supplier", component: () => import("../views/archive/Supplier.vue"), meta: { title: "供应商", perm: "supplier:list" } },
      { path: "archive/warehouse", component: () => import("../views/archive/Warehouse.vue"), meta: { title: "仓库管理", perm: "warehouse:list" } },
      { path: "archive/space", component: () => import("../views/archive/Space.vue"), meta: { title: "项目空间", perm: "space:list" } },
      { path: "archive/office", component: () => import("../views/archive/Office.vue"), meta: { title: "办公地点", perm: "office:list" } },
      { path: "system/org", component: () => import("../views/system/Org.vue"), meta: { title: "组织架构", perm: "sys:org" } },
      { path: "system/user", component: () => import("../views/system/User.vue"), meta: { title: "用户管理", perm: "sys:user" } },
      { path: "system/role", component: () => import("../views/system/Role.vue"), meta: { title: "角色管理", perm: "sys:role" } },
      { path: "system/menu", component: () => import("../views/system/Menu.vue"), meta: { title: "菜单管理", perm: "sys:menu" } },
      { path: "system/dict", component: () => import("../views/system/Dict.vue"), meta: { title: "字典管理", perm: "sys:dict" } },
      { path: "system/log", component: () => import("../views/system/Log.vue"), meta: { title: "操作日志", perm: "sys:log" } },
    ],
  },
  { path: "/:pathMatch(.*)*", redirect: "/dashboard" },
];

const router = createRouter({ history: createWebHistory(), routes });
export default router;

router.beforeEach((to) => {
  const token = localStorage.getItem("token");
  // 移动端 H5 页自带登录表单，允许无 token 访问
  const publicPaths = ["/login", "/m/stocktake", "/m/approval"];
  if (!publicPaths.includes(to.path) && !token) return "/login";
  if (to.path === "/login" && token) return "/dashboard";
  // 按钮级权限之外的路由级守卫：无页面权限时回驾驶舱（admin 通配放行）
  if (token && to.meta.perm && !useAuthStore().hasPerm(to.meta.perm)) {
    console.warn(`无权限访问：${to.path}（需要 ${to.meta.perm}）`);
    return "/dashboard";
  }
  document.title = to.meta.title ? `${to.meta.title} · 固定资产管理系统` : "固定资产管理系统";
});
