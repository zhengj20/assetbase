import { createApp } from "vue";
import { createPinia } from "pinia";
import ElementPlus from "element-plus";
import zhCn from "element-plus/es/locale/lang/zh-cn";
import * as Icons from "@element-plus/icons-vue";
import "element-plus/dist/index.css";
import App from "./App.vue";
import router from "./router";
import { useAuthStore } from "./stores/auth";
import "./styles/index.css";

const app = createApp(App);
app.use(createPinia());
app.use(router);
app.use(ElementPlus, { locale: zhCn });
for (const [name, comp] of Object.entries(Icons)) app.component(name, comp);
app.directive("perm", {
  mounted(el, binding) {
    const code = binding.value;
    if (code && !useAuthStore().hasPerm(code)) el.parentNode?.removeChild(el);
  },
});
app.mount("#app");
