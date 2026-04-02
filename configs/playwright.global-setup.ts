import type { FullConfig } from '@playwright/test';

type HealthOptions = {
  retries?: number;
  baseDelayMs?: number;
  timeoutMs?: number;
};

async function sleep(ms: number): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

async function assertServiceHealthy(url: string, options: HealthOptions = {}): Promise<void> {
  const retries = options.retries ?? 5;
  const baseDelayMs = options.baseDelayMs ?? 400;
  const timeoutMs = options.timeoutMs ?? 6_000;
  let lastError: unknown;

  for (let attempt = 1; attempt <= retries; attempt += 1) {
    try {
      const response = await fetch(url, { method: 'GET', redirect: 'follow', signal: AbortSignal.timeout(timeoutMs) });
      if (!response.ok) {
        throw new Error(`status=${response.status}`);
      }
      return;
    } catch (error) {
      lastError = error;
      if (attempt === retries) {
        break;
      }
      await sleep(baseDelayMs * Math.pow(2, attempt - 1));
    }
  }

  throw new Error(`E2E health check failed for ${url}: ${String(lastError)}`);
}

function toHealthUrl(baseURL: string): string {
  const trimmed = baseURL.replace(/\/+$/, '');
  return `${trimmed}/`;
}

export default async function globalSetup(config: FullConfig): Promise<void> {
  const projectURLs = new Set<string>();

  for (const project of config.projects) {
    const baseURL = project.use.baseURL;
    if (typeof baseURL === 'string' && baseURL.length > 0) {
      projectURLs.add(toHealthUrl(baseURL));
    }
  }

  await Promise.all(
    Array.from(projectURLs).map(async (url) => {
      await assertServiceHealthy(url);
      console.log(`[e2e-health] ready: ${url}`);
    })
  );
}
