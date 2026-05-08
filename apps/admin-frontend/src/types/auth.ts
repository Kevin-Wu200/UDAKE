export interface AuthUser {
  userId: number;
  email: string;
  role: string;
  permissions: string[];
  enterpriseId?: number | null;
}

export interface UserSessionPayload {
  accessToken: string;
  refreshToken: string;
  user: AuthUser;
}

export interface DeviceItem {
  deviceId: string;
  deviceName: string;
  deviceType: string;
  os: string;
  browser: string;
  ip: string;
  location: string;
  lastLoginAt: number;
  status: string;
  isCurrent: boolean;
}

export interface DevicePagination {
  page: number;
  pageSize: number;
  total: number;
}

export interface DeviceListResult {
  items: DeviceItem[];
  pagination: DevicePagination;
  currentDeviceId: string | null;
}
