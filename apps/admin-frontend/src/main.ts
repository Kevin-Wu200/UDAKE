import { createApp } from 'vue';
import { createPinia } from 'pinia';
import ElementPlus from 'element-plus';
import 'element-plus/dist/index.css';
import App from './App.vue';
import router from './router';
import { useAuthStore } from './stores/auth';
import './styles/index.css';

if (!window.location.hash && window.location.pathname === '/enterprise/login') {
  window.location.replace('/#/enterprise/login');
}

const app = createApp(App);
const pinia = createPinia();
document.title = import.meta.env.VITE_APP_TITLE;

app.use(pinia);
app.use(ElementPlus);
app.use(router);

const authStore = useAuthStore(pinia);
void authStore.bootstrapAuth();

app.mount('#app');
