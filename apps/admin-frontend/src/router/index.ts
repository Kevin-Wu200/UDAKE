import { createRouter, createWebHashHistory } from 'vue-router';
import { useAuthStore } from '../stores/auth';

const LoginView = () => import('../views/LoginView.vue');
const DashboardView = () => import('../views/DashboardView.vue');
const ProductKeysView = () => import('../views/ProductKeysView.vue');
const UsersView = () => import('../views/UsersView.vue');
const AuditLogsView = () => import('../views/AuditLogsView.vue');
const AdminLayout = () => import('../layouts/AdminLayout.vue');

const UserCenterLayout = () => import('../layouts/UserCenterLayout.vue');
const ForbiddenView = () => import('../views/ForbiddenView.vue');
const UserLoginView = () => import('../views/user/UserLoginView.vue');
const UserRegisterView = () => import('../views/user/UserRegisterView.vue');
const ForgotPasswordView = () => import('../views/user/ForgotPasswordView.vue');
const ChangePasswordView = () => import('../views/user/ChangePasswordView.vue');
const ChangeEmailView = () => import('../views/user/ChangeEmailView.vue');
const DeviceManagementView = () => import('../views/user/DeviceManagementView.vue');

const USER_ALLOWED_ROLES = ['user', 'company_admin', 'super_admin', 'admin'];

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/403',
      name: 'forbidden',
      component: ForbiddenView,
      meta: { requiresAuth: false }
    },
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: { requiresAuth: false }
    },
    {
      path: '/user/login',
      name: 'user-login',
      component: UserLoginView,
      meta: { requiresAuth: false, userGuestOnly: true }
    },
    {
      path: '/user/register',
      name: 'user-register',
      component: UserRegisterView,
      meta: { requiresAuth: false, userGuestOnly: true }
    },
    {
      path: '/user/forgot-password',
      name: 'user-forgot-password',
      component: ForgotPasswordView,
      meta: { requiresAuth: false, userGuestOnly: true }
    },
    {
      path: '/user',
      component: UserCenterLayout,
      redirect: '/user/devices',
      meta: {
        requiresUserAuth: true,
        requiredRoles: USER_ALLOWED_ROLES
      },
      children: [
        {
          path: 'devices',
          name: 'user-devices',
          component: DeviceManagementView,
          meta: {
            title: '设备管理',
            requiresUserAuth: true,
            requiredRoles: USER_ALLOWED_ROLES
          }
        },
        {
          path: 'change-password',
          name: 'user-change-password',
          component: ChangePasswordView,
          meta: {
            title: '修改密码',
            requiresUserAuth: true,
            requiredRoles: USER_ALLOWED_ROLES
          }
        },
        {
          path: 'change-email',
          name: 'user-change-email',
          component: ChangeEmailView,
          meta: {
            title: '修改邮箱',
            requiresUserAuth: true,
            requiredRoles: USER_ALLOWED_ROLES
          }
        }
      ]
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
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/user/login'
    }
  ]
});

let bootstrapTask: Promise<void> | null = null;

router.beforeEach(async (to) => {
  const authStore = useAuthStore();

  if (!authStore.bootstrapped) {
    if (!bootstrapTask) {
      bootstrapTask = authStore.bootstrapAuth().finally(() => {
        bootstrapTask = null;
      });
    }
    await bootstrapTask;
  }

  const loggedIn = authStore.isLoggedIn;
  const requiresAdminAuth = Boolean(to.meta.requiresAuth);
  const requiresUserAuth = Boolean(to.meta.requiresUserAuth);
  const userGuestOnly = Boolean(to.meta.userGuestOnly);

  if (to.path === '/login' && loggedIn) {
    return authStore.user ? '/user/devices' : '/dashboard';
  }

  if (userGuestOnly && loggedIn) {
    return authStore.user ? '/user/devices' : '/dashboard';
  }

  if ((requiresAdminAuth || requiresUserAuth) && !loggedIn) {
    return {
      path: requiresAdminAuth ? '/login' : '/user/login',
      query: { redirect: to.fullPath }
    };
  }

  if (requiresUserAuth) {
    let valid = await authStore.validateCurrentToken();
    if (!valid) {
      const refreshedToken = await authStore.refreshAccessToken();
      if (!refreshedToken) {
        authStore.clearToken();
        return {
          path: '/user/login',
          query: { redirect: to.fullPath }
        };
      }
      valid = await authStore.validateCurrentToken(true);
      if (!valid) {
        authStore.clearToken();
        return {
          path: '/user/login',
          query: { redirect: to.fullPath }
        };
      }
    }

    const requiredRoles = Array.isArray(to.meta.requiredRoles)
      ? (to.meta.requiredRoles as string[])
      : [];

    if (requiredRoles.length > 0) {
      const role = authStore.user?.role;
      if (!role || !requiredRoles.includes(role)) {
        return '/403';
      }
    }
  }

  if (requiresAdminAuth && !loggedIn) {
    return { path: '/login', query: { redirect: to.fullPath } };
  }

  return true;
});

export default router;
