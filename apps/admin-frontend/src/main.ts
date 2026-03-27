import { createApp } from 'vue';
import { createPinia } from 'pinia';
import ElementPlus from 'element-plus';
import App from './App.vue';
import router from './router';
import './styles/index.css';

const app = createApp(App);
const pinia = createPinia();
document.title = import.meta.env.VITE_APP_TITLE;
app.use(pinia);
app.use(ElementPlus);

app.use(router);
app.mount('#app');
