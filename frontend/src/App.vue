<template>
  <router-view />
</template>

<script setup>
import { onMounted } from "vue";
import { useAuthStore } from "./stores/auth";

const auth = useAuthStore();
// 已登录时刷新菜单：新增菜单无需重新登录即可显示
onMounted(() => {
  if (auth.isLogin) auth.refreshMenus();
});
</script>
