export type KeyType =
  | 'personal_trial'
  | 'personal_standard'
  | 'enterprise_trial'
  | 'enterprise_standard';
export type KeyStatus = 'unused' | 'active' | 'disabled' | 'expired';

export interface ProductKeyMetadata {
  generation_seed?: string;
  enterprise_name?: string;
  assigned_by?: string;
  notes?: string;
  assigned_user_name?: string;
}

export interface ProductKey {
  id: number;
  product_key: string;
  key_type: KeyType;
  key_sub_type: string;
  status: KeyStatus;
  total_quota: number;
  used_count: number;
  user_id?: number;
  company_id?: number;
  assigned_at?: string;
  expires_at?: string;
  metadata?: ProductKeyMetadata;
  created_at: string;
  updated_at: string;
}

export interface ProductKeyCreateForm {
  type: KeyType;
  count: number;
  user_id?: number;
  company_id?: number;
  metadata?: ProductKeyMetadata;
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
