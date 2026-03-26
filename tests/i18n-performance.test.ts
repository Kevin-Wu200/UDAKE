import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { I18n } from '../apps/frontend/js/utils/I18n.js';

describe('I18n 性能测试', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn()
    });
    vi.stubGlobal('navigator', {
      language: 'zh-CN'
    });
    vi.stubGlobal('document', {
      documentElement: {
        lang: 'zh-CN'
      }
    });
    I18n.init('zh-CN');
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('翻译查找应在合理时间内完成', () => {
    const start = performance.now();
    for (let i = 0; i < 20000; i += 1) {
      I18n.t('app.title');
      I18n.t('upload.success', { count: i });
      I18n.t('task.progress');
    }
    const duration = performance.now() - start;
    expect(duration).toBeLessThan(1500);
  });

  it('频繁语言切换应保持可接受性能', async () => {
    const locales = ['zh-CN', 'en-US', 'zh-TW', 'ja-JP', 'ko-KR'];
    const start = performance.now();

    for (let i = 0; i < 50; i += 1) {
      await I18n.setLocaleAsync(locales[i % locales.length]);
    }

    const duration = performance.now() - start;
    expect(duration).toBeLessThan(2500);
  });
});
