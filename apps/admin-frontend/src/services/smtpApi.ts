import { http, isMockApiEnabled } from './http';
import { fetchSmtpConfig as fetchSmtpConfigMock, saveSmtpConfig as saveSmtpConfigMock, testSmtpConnection as testSmtpConnectionMock } from './mockApi';
import type { SMTPConfig } from '../types/admin';

interface SmtpValidateResult {
  enabled: boolean;
  connected: boolean;
  authenticated: boolean;
  test_email_sent: boolean;
  error: string;
}

function mapValidateError(result: SmtpValidateResult): string {
  if (result.error?.trim()) {
    return result.error.trim();
  }
  if (!result.enabled) {
    return 'SMTP 配置不完整';
  }
  if (!result.connected) {
    return 'SMTP 服务器连接失败';
  }
  if (!result.authenticated) {
    return 'SMTP 认证失败';
  }
  return 'SMTP 测试失败';
}

function resolveLatencyMs(startMs: number): number {
  return Math.max(1, Math.round(performance.now() - startMs));
}

export async function fetchSmtpConfig(): Promise<SMTPConfig> {
  if (isMockApiEnabled()) {
    return fetchSmtpConfigMock();
  }
  const response = await http.get<SMTPConfig>('/workflow/notifications/smtp/config');
  return response.data;
}

export async function saveSmtpConfig(payload: SMTPConfig): Promise<SMTPConfig> {
  if (isMockApiEnabled()) {
    return saveSmtpConfigMock(payload);
  }
  const response = await http.put<SMTPConfig>('/workflow/notifications/smtp/config', payload);
  return response.data;
}

export async function testSmtpConnection(payload: SMTPConfig): Promise<{ success: boolean; latencyMs: number }> {
  if (isMockApiEnabled()) {
    return testSmtpConnectionMock(payload);
  }
  const started = performance.now();
  const response = await http.post<SmtpValidateResult>('/workflow/notifications/smtp/validate', {
    host: payload.host,
    port: payload.port,
    encryption: payload.encryption,
    username: payload.username,
    password: payload.password
  });
  const result = response.data;
  if (!result.connected || !result.authenticated) {
    throw new Error(mapValidateError(result));
  }
  return {
    success: true,
    latencyMs: resolveLatencyMs(started)
  };
}
