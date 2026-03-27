export type KeyType = 'trial' | 'standard' | 'enterprise';
export type KeyStatus = 'unused' | 'active' | 'disabled';

export interface ProductKey {
  id: number;
  key: string;
  type: KeyType;
  status: KeyStatus;
  usageCount: number;
  enterpriseName: string;
  createdAt: string;
}

export type UserRole = 'admin' | 'auditor' | 'viewer';

export interface UserDevice {
  name: string;
  os: string;
  lastActiveAt: string;
}

export interface LoginLog {
  time: string;
  ip: string;
  result: 'success' | 'failed';
}

export interface UserItem {
  id: number;
  username: string;
  email: string;
  role: UserRole;
  status: boolean;
  createdAt: string;
  lastLoginAt: string;
  devices: UserDevice[];
  loginLogs: LoginLog[];
}

export type AuditEventType =
  | 'create_key'
  | 'import_key'
  | 'update_user'
  | 'reset_password'
  | 'login'
  | 'delete_key';

export interface AuditLog {
  id: number;
  operator: string;
  eventType: AuditEventType;
  target: string;
  time: string;
  ip: string;
}

export interface DashboardStats {
  userGrowth: Array<{ date: string; count: number }>;
  keyUsage: { used: number; unused: number };
  activeUsers7d: number;
  enterpriseTotal: number;
  enterpriseActive: number;
  todayRegistrations: number;
  todayLogins: number;
}
