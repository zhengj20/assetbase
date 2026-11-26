// 登录态存取 + access 令牌静默刷新（独立模块，避免 api 与 store 循环依赖）
import axios from "axios";

export function getToken() {
  return localStorage.getItem("token") || "";
}

export function getRefreshToken() {
  return localStorage.getItem("refresh_token") || "";
}

export function setTokens(token, refreshToken) {
  if (token) localStorage.setItem("token", token);
  if (refreshToken) localStorage.setItem("refresh_token", refreshToken);
}

export function clearTokens() {
  localStorage.removeItem("token");
  localStorage.removeItem("refresh_token");
}

let refreshing = null;

export async function tryRefresh() {
  const rt = getRefreshToken();
  if (!rt) return false;
  refreshing ||= (async () => {
    try {
      const res = await axios.post("/api/v1/auth/refresh", { refresh_token: rt });
      setTokens(res.data.token, res.data.refresh_token);
      return true;
    } catch (err) {
      if (err.response?.status === 401) clearTokens();
      return false;
    } finally {
      refreshing = null;
    }
  })();
  return refreshing;
}
