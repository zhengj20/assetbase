import axios from "axios";
import { ElMessage } from "element-plus";
import { getToken, tryRefresh, clearTokens } from "../lib/auth-token";

export const http = axios.create({ baseURL: "/api/v1", timeout: 30000 });

function toLogin() {
  clearTokens();
  if (location.pathname !== "/login") location.href = "/login";
}

http.interceptors.request.use((cfg) => {
  const token = getToken();
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

http.interceptors.response.use(
  (res) => res.data,
  async (err) => {
    const resp = err.response;
    let msg = "网络异常，请稍后重试";
    if (resp) {
      if (resp.status === 401) {
        const original = err.config || {};
        const isRefresh = String(original.url || "").includes("/auth/refresh");
        // access 令牌过期：静默刷新后重放原请求（仅一次）
        if (!isRefresh && !original._retried) {
          const ok = await tryRefresh();
          if (ok) {
            original._retried = true;
            original.headers = original.headers || {};
            original.headers.Authorization = `Bearer ${getToken()}`;
            return http(original);
          }
        }
        toLogin();
        msg = null;
      } else {
        const d = resp.data?.detail;
        if (Array.isArray(d)) {
          // FastAPI 422：detail 为 [{loc, msg, type}] 数组，逐条展示
          msg = d.map((x) => x.msg || JSON.stringify(x.loc || [])).join("；");
        } else {
          msg = typeof d === "string" ? d : `请求失败（${resp.status}）`;
        }
      }
    }
    if (msg) ElMessage.error(msg);
    return Promise.reject(err);
  }
);

/** 带 Token 的文件下载（Excel 报表等） */
export async function download(url, filename) {
  const token = localStorage.getItem("token");
  if (!token) {
    ElMessage.error("登录态已失效，请重新登录");
    throw new Error("no token");
  }
  let res;
  try {
    res = await axios.get(`/api/v1${url}`, {
      responseType: "blob",
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch (err) {
    const r = err.response;
    if (r?.status === 401) {
      // 静默刷新后重试一次
      const ok = await tryRefresh();
      if (ok) {
        res = await axios.get(`/api/v1${url}`, {
          responseType: "blob",
          headers: { Authorization: `Bearer ${getToken()}` },
        });
      } else {
        toLogin();
        throw err;
      }
    }
    // 后端导出接口出错抛 HTTPException（JSON 错误体），因 responseType=blob 收到的是 blob
    let msg = `导出失败（${r?.status || "网络异常"}）`;
    if (r?.data && typeof r.data.text === "function") {
      try {
        const detail = JSON.parse(await r.data.text())?.detail;
        if (typeof detail === "string") msg = detail;
      } catch {
        /* 保持默认提示 */
      }
    }
    ElMessage.error(msg);
    throw err;
  }
  const blob = new Blob([res.data], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

// ================= 认证 =================
export const authApi = {
  login: (data) => http.post("/auth/login", data),
  me: () => http.get("/auth/me"),
  menus: () => http.get("/auth/menus"),
  changePassword: (data) => http.put("/auth/password", data),
};

// ================= 驾驶舱 =================
export const dashboardApi = { get: () => http.get("/dashboard") };

// ================= 全局搜索 =================
export const searchApi = {
  quick: (params) => http.get("/search/quick", { params }),
  assets: (params) => http.get("/search/assets", { params }),
};

// ================= 资产档案 =================
export const assetApi = {
  list: (params) => http.get("/assets", { params }),
  statsTree: () => http.get("/assets/stats/tree"),
  statsSpaceTree: () => http.get("/assets/stats/space-tree"),
  statsDetail: (params) => http.get("/assets/stats/detail", { params }),
  warehouseStock: () => http.get("/warehouse-stock/summary"),
  detail: (id) => http.get(`/assets/${id}`),
  logs: (id) => http.get(`/assets/${id}/logs`),
  create: (data) => http.post("/assets", data),
  update: (id, data) => http.put(`/assets/${id}`, data),
  batchUpdate: (data) => http.post("/assets/batch-update", data),
  remove: (id) => http.delete(`/assets/${id}`),
  reprint: (id) => http.post(`/assets/${id}/reprint-qrcode`),
  repair: (id, data) => http.post(`/assets/${id}/repair`, data),
  repairDone: (id) => http.post(`/assets/${id}/repair-done`),
  importTemplate: () => download("/assets/import-template", "资产导入模板.xlsx"),
  importFile: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return http.post("/assets/import", fd);
  },
  uploadImage: (id, file) => {
    const fd = new FormData();
    fd.append("file", file);
    return http.post(`/assets/${id}/images`, fd);
  },
  images: (id) => http.get(`/assets/${id}/images`),
  delImage: (id, imageId) => http.delete(`/assets/${id}/images/${imageId}`),
};

// ================= 折旧管理 =================
export const depApi = {
  list: (params) => http.get("/depreciations", { params }),
  calculate: (period) => http.post("/depreciations/calculate", { period: period || null }),
  reverse: (period) => http.post(`/depreciations/reverse/${period}`),
  lock: (period) => http.post(`/depreciations/lock/${period}`),
  unlock: (period) => http.post(`/depreciations/unlock/${period}`),
};

// ================= 消息中心 =================
export const msgApi = {
  list: (params) => http.get("/messages", { params }),
  unread: () => http.get("/messages/unread-count"),
  read: (id) => http.post(`/messages/${id}/read`),
  readAll: () => http.post("/messages/read-all"),
};

// ================= 审批流配置 =================
export const flowApi = {
  list: () => http.get("/flows"),
  create: (data) => http.post("/flows", data),
  save: (defId, data) => http.put(`/flows/${defId}`, data),
  setStatus: (defId, status) => http.post(`/flows/${defId}/status`, null, { params: { status } }),
  remove: (defId) => http.delete(`/flows/${defId}`),
  approvalConfig: () => http.get("/flows/approval-config"),
  setApprovalConfig: (bizType, flowEnabled) =>
    http.put(`/flows/approval-config/${bizType}`, { flow_enabled: flowEnabled }),
};

// ================= 资产组合包 =================
export const groupApi = {
  list: (params) => http.get("/asset-groups", { params }),
  detail: (id) => http.get(`/asset-groups/${id}`),
  create: (data) => http.post("/asset-groups", data),
  adjust: (id, data) => http.put(`/asset-groups/${id}`, data),
  dissolve: (id) => http.delete(`/asset-groups/${id}`),
};

// ================= 基础档案 =================
export const archiveApi = {
  categories: () => http.get("/categories"),
  saveCategory: (data) => (data.id ? http.put(`/categories/${data.id}`, data) : http.post("/categories", data)),
  delCategory: (id) => http.delete(`/categories/${id}`),
  suppliers: () => http.get("/suppliers"),
  saveSupplier: (data) => (data.id ? http.put(`/suppliers/${data.id}`, data) : http.post("/suppliers", data)),
  delSupplier: (id) => http.delete(`/suppliers/${id}`),
  warehouses: () => http.get("/warehouses"),
  saveWarehouse: (data) => (data.id ? http.put(`/warehouses/${data.id}`, data) : http.post("/warehouses", data)),
  delWarehouse: (id) => http.delete(`/warehouses/${id}`),
  warehouseStock: (id) => http.get(`/warehouses/${id}/stock`),
  spaces: (params) => http.get("/spaces", { params }),
  saveSpace: (data) => (data.id ? http.put(`/spaces/${data.id}`, data) : http.post("/spaces", data)),
  delSpace: (id) => http.delete(`/spaces/${id}`),
  offices: (params) => http.get("/offices", { params }),
  saveOffice: (data) => (data.id ? http.put(`/offices/${data.id}`, data) : http.post("/offices", data)),
  delOffice: (id) => http.delete(`/offices/${id}`),
};

// ================= 业务单据 =================
export const docApi = {
  purchases: (params) => http.get("/purchases", { params }),
  purchase: (id) => http.get(`/purchases/${id}`),
  createPurchase: (data) => http.post("/purchases", data),
  delPurchase: (id) => http.delete(`/purchases/${id}`),
  approvedPurchases: (params) => http.get("/purchases/approved", { params }),
  purchaseItemsForInbound: (id) => http.get(`/purchases/${id}/items-for-inbound`),
  stockIns: (params) => http.get("/stock-ins", { params }),
  stockIn: (id) => http.get(`/stock-ins/${id}`),
  createStockIn: (data) => http.post("/stock-ins", data),
  stockOuts: (params) => http.get("/stock-outs", { params }),
  stockOut: (id) => http.get(`/stock-outs/${id}`),
  createStockOut: (data) => http.post("/stock-outs", data),
  transfers: (params) => http.get("/transfers", { params }),
  transfer: (id) => http.get(`/transfers/${id}`),
  createTransfer: (data) => http.post("/transfers", data),
  borrows: (params) => http.get("/borrows", { params }),
  borrow: (id) => http.get(`/borrows/${id}`),
  createBorrow: (data) => http.post("/borrows", data),
  returnBorrow: (id, data) => http.post(`/borrows/${id}/return`, data),
  returns: (params) => http.get("/returns", { params }),
  returnDetail: (id) => http.get(`/returns/${id}`),
  createReturn: (data) => http.post("/returns", data),
  scraps: (params) => http.get("/scraps", { params }),
  scrap: (id) => http.get(`/scraps/${id}`),
  createScrap: (data) => http.post("/scraps", data),
  nextDocNo: (bizType) => http.get(`/docs/${bizType}/next-no`),
  submit: (bizType, id) => http.post(`/docs/${bizType}/${id}/submit`),
  cancel: (bizType, id) => http.post(`/docs/${bizType}/${id}/cancel`),
  manualApprove: (bizType, id, comment) =>
    http.post(`/docs/${bizType}/${id}/manual-approve`, { comment: comment || null }),
  todos: () => http.get("/approvals/todos"),
  dones: () => http.get("/approvals/dones"),
  mine: (params) => http.get("/approvals/mine", { params }),
  approve: (taskId, data) => http.post(`/approvals/${taskId}`, data),
  delegate: (taskId, data) => http.post(`/approvals/${taskId}/delegate`, data),
  instance: (id) => http.get(`/instances/${id}`),
  withdraw: (id) => http.post(`/instances/${id}/withdraw`),
  terminate: (id, reason) => http.post(`/instances/${id}/terminate`, { reason }),
  delInstance: (id) => http.delete(`/instances/${id}`),
};

// ================= 易耗品 =================
export const conApi = {
  items: (params) => http.get("/con/items", { params }),
  itemOptions: (params) => http.get("/con/items/options", { params }),
  item: (id) => http.get(`/con/items/${id}`),
  saveItem: (data) => (data.id ? http.put(`/con/items/${data.id}`, data) : http.post("/con/items", data)),
  delItem: (id) => http.delete(`/con/items/${id}`),
  stock: (params) => http.get("/con/stock", { params }),
  stockSummary: () => http.get("/con/stock/summary"),
  purchases: (params) => http.get("/con/purchases", { params }),
  purchase: (id) => http.get(`/con/purchases/${id}`),
  createPurchase: (data) => http.post("/con/purchases", data),
  delPurchase: (id) => http.delete(`/con/purchases/${id}`),
  inbounds: (params) => http.get("/con/inbounds", { params }),
  inbound: (id) => http.get(`/con/inbounds/${id}`),
  createInbound: (data) => http.post("/con/inbounds", data),
  delInbound: (id) => http.delete(`/con/inbounds/${id}`),
  issues: (params) => http.get("/con/issues", { params }),
  issue: (id) => http.get(`/con/issues/${id}`),
  createIssue: (data) => http.post("/con/issues", data),
  delIssue: (id) => http.delete(`/con/issues/${id}`),
};

// ================= 流程监控（审批中心） =================
export const monitorApi = {
  list: (params) => http.get("/monitor/instances", { params }),
  stats: () => http.get("/monitor/stats"),
};

// ================= 盘点 =================
export const checkApi = {
  tasks: (params) => http.get("/check-tasks", { params }),
  task: (id) => http.get(`/check-tasks/${id}`),
  createTask: (data) => http.post("/check-tasks", data),
  items: (id, params) => http.get(`/check-tasks/${id}/items`, { params }),
  scan: (taskId, qrcode) => http.get(`/check-tasks/${taskId}/scan`, { params: { qrcode } }),
  record: (itemId, data) => http.post(`/check-items/${itemId}/record`, data),
  surplus: (taskId, data) => http.post(`/check-tasks/${taskId}/surplus`, data),
  finish: (taskId) => http.post(`/check-tasks/${taskId}/finish`),
  handleDiff: (taskId) => http.post(`/check-tasks/${taskId}/handle-diff`),
  summary: (taskId) => http.get(`/check-tasks/${taskId}/summary`),
};

// ================= 系统管理 =================
export const sysApi = {
  orgs: () => http.get("/orgs"),
  saveOrg: (data) => (data.id ? http.put(`/orgs/${data.id}`, data) : http.post("/orgs", data)),
  delOrg: (id) => http.delete(`/orgs/${id}`),
  users: (params) => http.get("/users", { params }),
  saveUser: (data) => (data.id ? http.put(`/users/${data.id}`, data) : http.post("/users", data)),
  delUser: (id) => http.delete(`/users/${id}`),
  roles: () => http.get("/roles"),
  saveRole: (data) => (data.id ? http.put(`/roles/${data.id}`, data) : http.post("/roles", data)),
  delRole: (id) => http.delete(`/roles/${id}`),
  roleMenuIds: (id) => http.get(`/roles/${id}/menu-ids`),
  menus: () => http.get("/menus"),
  saveMenu: (data) => (data.id ? http.put(`/menus/${data.id}`, data) : http.post("/menus", data)),
  delMenu: (id) => http.delete(`/menus/${id}`),
  dictTypes: () => http.get("/dict-types"),
  saveDictType: (data) => (data.id ? http.put(`/dict-types/${data.id}`, data) : http.post("/dict-types", data)),
  dict: (code) => http.get(`/dicts/${code}`),
  dictDatas: (dictId) => http.get("/dict-datas", { params: { dict_id: dictId } }),
  saveDictData: (data) => (data.id ? http.put(`/dict-datas/${data.id}`, data) : http.post("/dict-datas", data)),
  delDictData: (id) => http.delete(`/dict-datas/${id}`),
  logs: (params) => http.get("/logs", { params }),
};

// ================= 工作台 =================
export const workbenchApi = {
  summary: () => http.get("/workbench/summary"),
  calendar: (params) => http.get("/workbench/calendar", { params }),
  calendarRange: (params) => http.get("/workbench/calendar-range", { params }),
  workRecords: (params) => http.get("/workbench/work-records", { params }),
  createWorkRecord: (data) => http.post("/workbench/work-records", data),
  delWorkRecord: (id) => http.delete(`/workbench/work-records/${id}`),
};
