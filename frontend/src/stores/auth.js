import { defineStore } from "pinia";
import { authApi } from "../api";
import { setTokens } from "../lib/auth-token";

function safeParse(key, fallback) {
  try {
    const v = JSON.parse(localStorage.getItem(key) || "null");
    return v === null ? fallback : v;
  } catch {
    return fallback;
  }
}

export const useAuthStore = defineStore("auth", {
  state: () => ({
    token: localStorage.getItem("token") || "",
    user: safeParse("user", null),
    perms: safeParse("perms", []),
    menus: safeParse("menus", []),
  }),
  getters: {
    isLogin: (s) => !!s.token,
    isSuperAdmin: (s) => s.perms.includes("*"),
    hasPerm: (s) => (code) =>
      s.perms.includes("*") || !code || s.perms.includes(code),
  },
  actions: {
    async login(form) {
      const res = await authApi.login(form);
      this.token = res.token;
      this.user = res.user;
      this.perms = res.perms || [];
      setTokens(res.token, res.refresh_token);
      localStorage.setItem("user", JSON.stringify(res.user));
      localStorage.setItem("perms", JSON.stringify(res.perms || []));
      const menus = await authApi.menus();
      this.menus = menus;
      localStorage.setItem("menus", JSON.stringify(menus));
    },
    async refreshMenus() {
      if (!this.token) return;
      try {
        const menus = await authApi.menus();
        this.menus = menus;
        localStorage.setItem("menus", JSON.stringify(menus));
      } catch {
        /* 保留本地缓存菜单 */
      }
    },
    logout() {
      this.token = "";
      this.user = null;
      this.perms = [];
      this.menus = [];
      ["token", "refresh_token", "user", "perms", "menus"].forEach((k) => localStorage.removeItem(k));
    },
  },
});
