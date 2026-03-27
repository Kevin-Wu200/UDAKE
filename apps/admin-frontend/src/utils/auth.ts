export type PasswordStrengthLevel = 'weak' | 'medium' | 'strong';

export interface PasswordStrengthResult {
  level: PasswordStrengthLevel;
  score: number;
  label: string;
  color: string;
  requirements: string[];
}

export interface DeviceInfoPayload {
  device_id: string;
  fingerprint: string;
  platform: string;
  device_name: string;
  screen_resolution: string;
  timezone: string;
  language: string;
  canvas_fingerprint: string;
}

export function decodeJwtPayload(token: string): Record<string, unknown> | null {
  const chunks = token.split('.');
  if (chunks.length !== 3) {
    return null;
  }

  try {
    const base64 = chunks[1].replace(/-/g, '+').replace(/_/g, '/');
    const pad = base64.length % 4;
    const padded = pad ? base64.padEnd(base64.length + (4 - pad), '=') : base64;
    const json = decodeURIComponent(
      atob(padded)
        .split('')
        .map((char) => `%${`00${char.charCodeAt(0).toString(16)}`.slice(-2)}`)
        .join('')
    );
    return JSON.parse(json) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export function getTokenExpireAtMs(token: string): number | null {
  const payload = decodeJwtPayload(token);
  const exp = Number(payload?.exp);
  if (!Number.isFinite(exp) || exp <= 0) {
    return null;
  }
  return exp * 1000;
}

export function evaluatePasswordStrength(password: string): PasswordStrengthResult {
  const requirements: string[] = [];
  if (password.length < 8) {
    requirements.push('至少8位');
  }
  if (!/[a-z]/.test(password)) {
    requirements.push('至少1个小写字母');
  }
  if (!/[A-Z]/.test(password)) {
    requirements.push('至少1个大写字母');
  }
  if (!/\d/.test(password)) {
    requirements.push('至少1个数字');
  }

  const score = 4 - requirements.length;
  if (score <= 1) {
    return {
      level: 'weak',
      score: 33,
      label: '弱',
      color: '#ef4444',
      requirements
    };
  }

  if (score <= 3) {
    return {
      level: 'medium',
      score: 66,
      label: '中',
      color: '#f59e0b',
      requirements
    };
  }

  return {
    level: 'strong',
    score: 100,
    label: '强',
    color: '#22c55e',
    requirements
  };
}

function simpleHash(input: string): string {
  let hash = 0;
  for (let i = 0; i < input.length; i += 1) {
    hash = (hash << 5) - hash + input.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash).toString(36);
}

export function buildDeviceInfoPayload(): DeviceInfoPayload {
  const screenResolution = `${window.screen.width}x${window.screen.height}`;
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  const language = navigator.language || 'zh-CN';
  const ua = navigator.userAgent || 'unknown';
  const canvasFingerprint = simpleHash(`${ua}|${screenResolution}|${timezone}|${language}`);
  const fingerprint = simpleHash(`fp|${ua}|${screenResolution}|${timezone}|${language}|${canvasFingerprint}`);

  return {
    device_id: `web-${fingerprint}`,
    fingerprint,
    platform: 'web',
    device_name: navigator.platform || 'Web Device',
    screen_resolution: screenResolution,
    timezone,
    language,
    canvas_fingerprint: canvasFingerprint
  };
}

export function encodeRememberPassword(rawPassword: string): string {
  const bytes = new TextEncoder().encode(rawPassword);
  const binary = Array.from(bytes)
    .map((item) => String.fromCharCode(item))
    .join('');
  return btoa(binary);
}

export function decodeRememberPassword(encodedPassword: string): string {
  try {
    const binary = atob(encodedPassword);
    const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
    return new TextDecoder().decode(bytes);
  } catch {
    return '';
  }
}

export function formatUnixTime(timestamp: number): string {
  if (!timestamp) {
    return '-';
  }
  const date = new Date(timestamp * 1000);
  const y = date.getFullYear();
  const m = `${date.getMonth() + 1}`.padStart(2, '0');
  const d = `${date.getDate()}`.padStart(2, '0');
  const hh = `${date.getHours()}`.padStart(2, '0');
  const mm = `${date.getMinutes()}`.padStart(2, '0');
  const ss = `${date.getSeconds()}`.padStart(2, '0');
  return `${y}-${m}-${d} ${hh}:${mm}:${ss}`;
}
