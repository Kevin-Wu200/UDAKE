import { expect, type Locator, type Page, type Response } from '@playwright/test';

type RetryOptions = {
  retries?: number;
  baseDelayMs?: number;
  context?: string;
  shouldRetry?: (error: unknown, attempt: number) => boolean;
};

type WaitForConditionOptions = {
  timeoutMs?: number;
  intervalMs?: number;
  message?: string;
};

type WaitForApiResponseOptions = {
  timeoutMs?: number;
};

export class TestDataFactory {
  private readonly namespace: string;
  private sequence = 0;
  private readonly usedIds = new Set<string>();

  constructor(namespace: string) {
    this.namespace = namespace;
  }

  nextId(prefix: string): string {
    this.sequence += 1;
    const id = `${prefix}_${this.namespace}_${Date.now()}_${this.sequence}`;
    this.usedIds.add(id);
    return id;
  }

  user(overrides: Partial<{ username: string; email: string; password: string; role: string }> = {}) {
    const id = this.nextId('user');
    return {
      username: `${id}`,
      email: `${id}@example.com`,
      password: 'Test123!@#',
      role: 'user',
      ...overrides
    };
  }

  clear(): void {
    this.usedIds.clear();
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function retryWithBackoff<T>(
  operation: () => Promise<T>,
  { retries = 3, baseDelayMs = 300, context = 'operation', shouldRetry }: RetryOptions = {}
): Promise<T> {
  let lastError: unknown;

  for (let attempt = 1; attempt <= retries; attempt += 1) {
    try {
      return await operation();
    } catch (error) {
      lastError = error;
      const canRetry = attempt < retries && (shouldRetry ? shouldRetry(error, attempt) : true);

      console.warn(`[e2e-retry] ${context} failed on attempt ${attempt}/${retries}`);
      if (!canRetry) {
        break;
      }

      const delayMs = baseDelayMs * Math.pow(2, attempt - 1);
      console.log(`[e2e-retry] retry ${context} in ${delayMs}ms`);
      await sleep(delayMs);
    }
  }

  throw lastError instanceof Error
    ? lastError
    : new Error(`[e2e-retry] ${context} failed after ${retries} attempts`);
}

export async function waitForCondition(
  condition: () => Promise<boolean> | boolean,
  { timeoutMs = 30_000, intervalMs = 300, message = 'condition not met before timeout' }: WaitForConditionOptions = {}
): Promise<void> {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if (await condition()) {
      return;
    }
    await sleep(intervalMs);
  }

  throw new Error(`[e2e-wait] ${message}, timeout=${timeoutMs}ms`);
}

export async function gotoAndWaitForAppReady(
  page: Page,
  url: string,
  readyLocator: Locator,
  timeoutMs = 30_000
): Promise<void> {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: timeoutMs });
  await expect(readyLocator).toBeVisible({ timeout: timeoutMs });
}

export async function waitForApiResponse(
  page: Page,
  matcher: RegExp | string,
  action: () => Promise<void>,
  { timeoutMs = 15_000 }: WaitForApiResponseOptions = {}
): Promise<Response> {
  const responsePromise = page.waitForResponse(
    (response) => {
      const request = response.request();
      const target = response.url();
      if (typeof matcher === 'string') {
        return target.includes(matcher) && request.method() !== 'OPTIONS';
      }
      return matcher.test(target) && request.method() !== 'OPTIONS';
    },
    { timeout: timeoutMs }
  );

  await action();
  const response = await responsePromise;
  expect(response.ok(), `API response not ok: ${response.url()}`).toBeTruthy();
  return response;
}

export function createTestDataFactory(scope: string): TestDataFactory {
  return new TestDataFactory(scope.replace(/[^a-zA-Z0-9_\-]/g, '_'));
}
