import { createRouter, createWebHashHistory } from 'vue-router';
import { isAdminRole, useAuthStore } from '../stores/auth';
import { resolveLoginRouteByContext } from '../utils/authRedirect';

const AdminLoginView = () => import('../views/Login/AdminLogin.vue');
const EnterpriseLoginView = () => import('../views/Login/EnterpriseLogin.vue');
const DashboardView = () => import('../views/DashboardView.vue');
const ProductKeysView = () => import('../views/ProductKeysView.vue');
const CompanyProductKeysView = () => import('../views/CompanyProductKeysView.vue');
const CompanyAdminProfileView = () => import('../views/CompanyAdminProfile.vue');
const SMTPSettingsView = () => import('../views/SMTPSettings.vue');
const EmailLogsView = () => import('../views/EmailLogs.vue');
const UsersView = () => import('../views/UsersView.vue');
const AuditLogsView = () => import('../views/AuditLogsView.vue');
const EnterpriseManagementView = () => import('../views/EnterpriseManagementView.vue');
const TicketsView = () => import('../views/TicketsView.vue');
const TicketDetailView = () => import('../views/TicketDetailView.vue');
const WorkflowListView = () => import('../views/workflow/WorkflowList.vue');
const WorkflowEditorView = () => import('../views/workflow/WorkflowEditor.vue');
const HistoryAnalysisLayoutView = () => import('../views/history-analysis/HistoryAnalysisLayout.vue');
const HistorySectionView = () => import('../views/history-analysis/HistorySectionView.vue');
const AdminLayout = () => import('../layouts/AdminLayout.vue');
const EnterpriseLayout = () => import('../layouts/EnterpriseLayout.vue');

const UserCenterLayout = () => import('../layouts/UserCenterLayout.vue');
const ForbiddenView = () => import('../views/ForbiddenView.vue');
const UserLoginView = () => import('../views/user/UserLoginView.vue');
const UserRegisterView = () => import('../views/user/UserRegisterView.vue');
const ForgotPasswordView = () => import('../views/user/ForgotPasswordView.vue');
const ChangePasswordView = () => import('../views/user/ChangePasswordView.vue');
const ChangeEmailView = () => import('../views/user/ChangeEmailView.vue');
const DeviceManagementView = () => import('../views/user/DeviceManagementView.vue');

const USER_ALLOWED_ROLES = ['user', 'company_admin', 'super_admin', 'admin'];
const ADMIN_ALLOWED_ROLES = ['company_admin', 'super_admin', 'admin'];
const CONSOLE_ALLOWED_ROLES = [...ADMIN_ALLOWED_ROLES]; // Removed enterprise from here
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
      path: '/login/admin',
      name: 'login-admin',
      component: AdminLoginView,
      meta: { requiresAuth: false }
    },
    {
      path: '/login/enterprise',
      name: 'login-enterprise',
      component: EnterpriseLoginView,
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
      path: '/enterprise',
      component: EnterpriseLayout,
      meta: { requiresAuth: true, roles: ['enterprise'], requiredRoles: ['enterprise'] },
      redirect: '/enterprise/dashboard',
      children: [
        {
          path: 'dashboard',
          name: 'enterprise-dashboard',
          component: DashboardView,
          meta: { titleKey: 'dashboard', breadcrumbKey: 'dashboard', roles: ['enterprise'] }
        },
        {
          path: 'management',
          name: 'enterprise-management',
          component: EnterpriseManagementView,
          meta: {
            title: '企业管理',
            breadcrumbKey: 'dashboard',
            roles: ['enterprise'],
            requiredRoles: ['enterprise']
          }
        },
        {
          path: 'workflows',
          name: 'enterprise-workflows',
          component: WorkflowListView,
          meta: { titleKey: 'workflowEngine', breadcrumbKey: 'workflowEngine', roles: ['enterprise'] }
        },
        {
          path: 'users',
          name: 'enterprise-users',
          component: UsersView,
          meta: { titleKey: 'users', breadcrumbKey: 'users', roles: ['enterprise'] }
        },
        {
          path: 'tickets',
          name: 'enterprise-tickets',
          component: TicketsView,
          meta: { titleKey: 'tickets', breadcrumbKey: 'tickets', roles: ['enterprise'] }
        },
        {
          path: 'tickets/:id',
          name: 'enterprise-ticket-detail',
          component: TicketDetailView,
          meta: { titleKey: 'ticketDetail', breadcrumbKey: 'ticketDetail', roles: ['enterprise'] }
        }
      ]
    },
    {
      path: '/',
      component: AdminLayout,
      meta: { requiresAuth: true, roles: ADMIN_ALLOWED_ROLES, requiredRoles: ADMIN_ALLOWED_ROLES },
      redirect: '/dashboard',
      children: [
        {
          path: '/dashboard',
          name: 'dashboard',
          component: DashboardView,
          meta: { titleKey: 'dashboard', breadcrumbKey: 'dashboard', roles: ADMIN_ALLOWED_ROLES }
        },
        {
          path: '/product-keys',
          name: 'product-keys',
          component: ProductKeysView,
          meta: {
            titleKey: 'productKeys',
            breadcrumbKey: 'productKeys',
            roles: ['super_admin', 'admin'],
            requiredRoles: ['super_admin', 'admin']
          }
        },
        {
          path: '/company/product-keys',
          name: 'company-product-keys',
          component: CompanyProductKeysView,
          meta: {
            titleKey: 'companyProductKeys',
            breadcrumbKey: 'companyProductKeys',
            requiresAuth: true,
            roles: ['company_admin'],
            requiredRoles: ['company_admin']
          }
        },
        {
          path: '/company/profile',
          name: 'company-profile',
          component: CompanyAdminProfileView,
          meta: {
            titleKey: 'companyProfile',
            requiresAuth: true,
            roles: ['company_admin'],
            requiredRoles: ['company_admin']
          }
        },
        {
          path: '/smtp-settings',
          name: 'smtp-settings',
          component: SMTPSettingsView,
          meta: {
            titleKey: 'smtpconfig',
            roles: ['super_admin', 'admin'],
            requiredRoles: ['super_admin', 'admin']
          }
        },
        {
          path: '/email-logs',
          name: 'email-logs',
          component: EmailLogsView,
          meta: {
            titleKey: 'emaillog',
            roles: ['super_admin', 'admin'],
            requiredRoles: ['super_admin', 'admin']
          }
        },
        {
          path: '/workflows',
          name: 'workflows',
          component: WorkflowListView,
          meta: { titleKey: 'workflowEngine', breadcrumbKey: 'workflowEngine', roles: ADMIN_ALLOWED_ROLES }
        },
        {
          path: '/workflows/editor/:workflowId?',
          name: 'workflow-editor',
          component: WorkflowEditorView,
          meta: { titleKey: 'workflowEditor', breadcrumbKey: 'workflowEditor', roles: ADMIN_ALLOWED_ROLES }
        },
        {
          path: '/history-analysis',
          component: HistoryAnalysisLayoutView,
          redirect: '/history-analysis/snapshots',
          meta: {
            titleKey: 'historyAnalysis',
            breadcrumbKey: 'historyAnalysis',
            roles: ADMIN_ALLOWED_ROLES,
            requiredRoles: ADMIN_ALLOWED_ROLES
          },
          children: [
            {
              path: 'snapshots',
              name: 'history-analysis-snapshots',
              component: HistorySectionView,
              props: { section: 'snapshots' },
              meta: {
                titleKey: 'historyAnalysisSnapshots',
                breadcrumbKey: 'historyAnalysisSnapshots',
                requiredRoles: ADMIN_ALLOWED_ROLES,
                keepAlive: true
              }
            },
            {
              path: 'compare',
              name: 'history-analysis-compare',
              component: HistorySectionView,
              props: { section: 'compare' },
              meta: {
                titleKey: 'historyAnalysisCompare',
                breadcrumbKey: 'historyAnalysisCompare',
                requiredRoles: ADMIN_ALLOWED_ROLES,
                keepAlive: true
              }
            },
            {
              path: 'trend',
              name: 'history-analysis-trend',
              component: HistorySectionView,
              props: { section: 'trend' },
              meta: {
                titleKey: 'historyAnalysisTrend',
                breadcrumbKey: 'historyAnalysisTrend',
                requiredRoles: ADMIN_ALLOWED_ROLES,
                keepAlive: true
              }
            },
            {
              path: 'anomaly',
              name: 'history-analysis-anomaly',
              component: HistorySectionView,
              props: { section: 'anomaly' },
              meta: {
                titleKey: 'historyAnalysisAnomaly',
                breadcrumbKey: 'historyAnalysisAnomaly',
                requiredRoles: ADMIN_ALLOWED_ROLES,
                keepAlive: true
              }
            },
            {
              path: 'forecast',
              name: 'history-analysis-forecast',
              component: HistorySectionView,
              props: { section: 'forecast' },
              meta: {
                titleKey: 'historyAnalysisForecast',
                breadcrumbKey: 'historyAnalysisForecast',
                requiredRoles: ADMIN_ALLOWED_ROLES,
                keepAlive: true
              }
            },
            {
              path: 'reports',
              name: 'history-analysis-reports',
              component: HistorySectionView,
              props: { section: 'reports' },
              meta: {
                titleKey: 'historyAnalysisReports',
                breadcrumbKey: 'historyAnalysisReports',
                requiredRoles: ADMIN_ALLOWED_ROLES,
                keepAlive: true
              }
            }
          ]
        },
        {
          path: '/users',
          name: 'users',
          component: UsersView,
          meta: { titleKey: 'users', breadcrumbKey: 'users', roles: ADMIN_ALLOWED_ROLES }
        },
        {
          path: '/tickets',
          name: 'tickets',
          component: TicketsView,
          meta: { titleKey: 'tickets', breadcrumbKey: 'tickets', roles: ADMIN_ALLOWED_ROLES }
        },
        {
          path: '/tickets/:id',
          name: 'ticket-detail',
          component: TicketDetailView,
          meta: { titleKey: 'ticketDetail', breadcrumbKey: 'ticketDetail', roles: ADMIN_ALLOWED_ROLES }
        },
        {
          path: '/audit-logs',
          name: 'audit-logs',
          component: AuditLogsView,
          meta: { titleKey: 'auditLogs', breadcrumbKey: 'auditLogs', roles: ADMIN_ALLOWED_ROLES }
        }
      ]
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/login/enterprise'
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
  const hasAdminAccess = authStore.isLegacyAdminSession || isAdminRole(authStore.user?.role);
  const hasEnterpriseAccess = authStore.user?.role === 'enterprise';
  const requiredRoles = Array.isArray(to.meta.roles)
    ? (to.meta.roles as string[])
    : Array.isArray(to.meta.requiredRoles)
      ? (to.meta.requiredRoles as string[])
    : [];
  const requiresEnterpriseOnly = requiredRoles.length > 0 && requiredRoles.every((role) => role === 'enterprise');

  if ((to.path === '/login/admin' || to.path === '/login/enterprise') && loggedIn) {
    if (hasEnterpriseAccess) {
      return '/enterprise/dashboard';
    }
    return hasAdminAccess ? '/dashboard' : '/user/devices';
  }

  if (userGuestOnly && loggedIn) {
    return hasAdminAccess ? '/dashboard' : '/user/devices';
  }

  if ((requiresAdminAuth || requiresUserAuth) && !loggedIn) {
    return {
      path: requiresUserAuth
        ? resolveLoginRouteByContext('user')
        : (requiresEnterpriseOnly ? resolveLoginRouteByContext('enterprise') : resolveLoginRouteByContext('admin')),
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
  }

  if (requiresAdminAuth && !loggedIn) {
    return { path: '/login/admin', query: { redirect: to.fullPath } };
  }

  if (requiredRoles.length > 0 && !authStore.isLegacyAdminSession) {
    const role = authStore.user?.role;
    if (!role || !requiredRoles.includes(role)) {
      if (to.path === '/dashboard' && role === 'enterprise') {
        return '/enterprise/dashboard';
      }
      return '/403';
    }
  }

  return true;
});

export default router;
