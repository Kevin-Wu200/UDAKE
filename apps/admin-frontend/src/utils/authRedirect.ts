export type LoginEntryPath = '/login/admin' | '/login/enterprise' | '/user/login';

const LOGIN_REDIRECT_MAP: Record<LoginEntryPath, string> = {
  '/login/admin': '/dashboard',
  '/login/enterprise': '/enterprise-management',
  '/user/login': '/user/devices'
};

export function resolveLoginFallbackRedirect(path: string): string {
  if (path in LOGIN_REDIRECT_MAP) {
    return LOGIN_REDIRECT_MAP[path as LoginEntryPath];
  }
  return '/dashboard';
}

export function resolveLoginRouteByContext(context: 'enterprise' | 'user' | 'admin'): LoginEntryPath {
  if (context === 'enterprise') {
    return '/login/enterprise';
  }
  if (context === 'user') {
    return '/user/login';
  }
  return '/login/admin';
}
