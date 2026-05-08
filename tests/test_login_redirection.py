from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding='utf-8')


def test_login_routes_are_split():
    router = _read('apps/admin-frontend/src/router/index.ts')
    assert "path: '/login/admin'" in router
    assert "component: AdminLoginView" in router
    assert "path: '/login/enterprise'" in router
    assert "component: EnterpriseLoginView" in router
    assert "path: '/user/login'" in router
    assert "component: UserLoginView" in router


def test_auth_service_login_context_payload():
    admin_auth_api = _read('apps/admin-frontend/src/services/userAuthApi.ts')
    frontend_auth_service = _read('apps/frontend/js/services/AuthService.ts')

    assert 'context,' in admin_auth_api
    assert "loginUser(email: string, password: string, context: LoginContext = 'admin')" in admin_auth_api
    assert 'context: loginContext,' in frontend_auth_service


def test_redirect_mapping_and_explicit_redirect_usage():
    redirect_util = _read('apps/admin-frontend/src/utils/authRedirect.ts')
    admin_login_view = _read('apps/admin-frontend/src/views/Login/AdminLogin.vue')
    enterprise_login_view = _read('apps/admin-frontend/src/views/Login/EnterpriseLogin.vue')
    user_login_view = _read('apps/admin-frontend/src/views/user/UserLoginView.vue')

    assert "'/login/admin': '/dashboard'" in redirect_util
    assert "'/login/enterprise': '/enterprise-management'" in redirect_util
    assert "'/user/login': '/user/devices'" in redirect_util

    assert 'resolveLoginFallbackRedirect(route.path)' in admin_login_view
    assert 'resolveLoginFallbackRedirect(route.path)' in enterprise_login_view
    assert 'resolveLoginFallbackRedirect(route.path)' in user_login_view
