import { createRouter, createWebHashHistory } from 'vue-router';
import { useAuthStore } from '../stores/auth';

const LoginView = () => import('../views/LoginView.vue');
const DashboardView = () => import('../views/DashboardView.vue');
const ProductKeysView = () => import('../views/ProductKeysView.vue');
const UsersView = () => import('../views/UsersView.vue');
const AuditLogsView = () => import('../views/AuditLogsView.vue');
const AdminLayout = () => import('../layouts/AdminLayout.vue');

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: { requiresAuth: false }
    },
    {
      path: '/',
      component: AdminLayout,
      meta: { requiresAuth: true },
      redirect: '/dashboard',
      children: [
        {
          path: '/dashboard',
          name: 'dashboard',
          component: DashboardView,
          meta: { title: '统计概览' }
        },
        {
          path: '/product-keys',
          name: 'product-keys',
          component: ProductKeysView,
          meta: { title: '产品密钥管理' }
        },
        { path: '/users', name: 'users', component: UsersView, meta: { title: '用户管理' } },
        { path: '/audit-logs', name: 'audit-logs', component: AuditLogsView, meta: { title: '审计日志' } }
      ]
    }
  ]
});

router.beforeEach((to) => {
  const authStore = useAuthStore();
  const loggedIn = authStore.isLoggedIn;

  if (to.path === '/login' && loggedIn) {
    return '/dashboard';
  }

  if (to.meta.requiresAuth && !loggedIn) {
    return { path: '/login', query: { redirect: to.fullPath } };
  }

  return true;
});

export default router;
