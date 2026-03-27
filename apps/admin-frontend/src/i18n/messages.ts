import type { AppLanguage } from '../stores/app';

const messages: Record<AppLanguage, Record<string, string>> = {
  'zh-CN': {
    appTitle: '管理员后台',
    dashboard: '统计概览',
    productKeys: '产品密钥管理',
    users: '用户管理',
    auditLogs: '审计日志',
    logout: '退出登录',
    login: '登录',
    username: '用户名',
    password: '密码',
    rememberPassword: '记住密码',
    loginSuccess: '登录成功',
    requiredUsername: '请输入用户名',
    requiredPassword: '请输入密码'
  },
  'en-US': {
    appTitle: 'Admin Console',
    dashboard: 'Dashboard',
    productKeys: 'Product Keys',
    users: 'Users',
    auditLogs: 'Audit Logs',
    logout: 'Sign Out',
    login: 'Sign In',
    username: 'Username',
    password: 'Password',
    rememberPassword: 'Remember password',
    loginSuccess: 'Login success',
    requiredUsername: 'Please enter username',
    requiredPassword: 'Please enter password'
  }
};

export function translate(language: AppLanguage, key: string): string {
  return messages[language][key] ?? key;
}
