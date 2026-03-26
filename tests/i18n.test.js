import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { I18n } from '../apps/frontend/js/utils/I18n.js';

describe('I18n', () => {
    beforeEach(() => {
        // Mock localStorage
        global.localStorage = {
            getItem: vi.fn(),
            setItem: vi.fn(),
            removeItem: vi.fn(),
            clear: vi.fn()
        };
        
        // Mock navigator
        global.navigator = {
            language: 'zh-CN'
        };
        
        // Mock document
        global.document = {
            documentElement: {
                lang: 'zh-CN'
            }
        };
    });

    afterEach(() => {
        vi.clearAllMocks();
    });

    describe('初始化', () => {
        it('应该使用默认语言初始化', () => {
            I18n.init();
            expect(I18n.locale).toBe('zh-CN');
        });

        it('应该从localStorage读取保存的语言', () => {
            localStorage.getItem.mockReturnValue('en-US');
            I18n.init();
            expect(I18n.locale).toBe('en-US');
        });

        it('应该使用传入的语言参数', () => {
            I18n.init('en-US');
            expect(I18n.locale).toBe('en-US');
        });

        it('应该规范化不支持的语言代码', () => {
            I18n.init('fr-FR');
            expect(I18n.locale).toBe('en-US');
        });

        it('应该规范化zh开头的语言代码为zh-CN', () => {
            I18n.init('zh-TW');
            expect(I18n.locale).toBe('zh-TW');
        });
    });

    describe('语言切换', () => {
        beforeEach(() => {
            I18n.init();
        });

        it('应该能够切换语言', () => {
            I18n.setLocale('en-US');
            expect(I18n.locale).toBe('en-US');
        });

        it('切换语言时应该保存到localStorage', () => {
            I18n.setLocale('en-US');
            expect(localStorage.setItem).toHaveBeenCalledWith('udake_locale', 'en-US');
        });

        it('切换语言时应该更新document.lang', () => {
            I18n.setLocale('en-US');
            expect(document.documentElement.lang).toBe('en');
        });

        it('应该拒绝切换到不支持的语言', () => {
            const originalLocale = I18n.locale;
            I18n.setLocale('fr-FR');
            expect(I18n.locale).toBe(originalLocale);
        });

        it('应该在语言变化时通知监听器', () => {
            const callback = vi.fn();
            I18n.onChange(callback);
            
            I18n.setLocale('en-US');
            expect(callback).toHaveBeenCalledWith('en-US');
        });
    });

    describe('翻译获取', () => {
        beforeEach(() => {
            I18n.init();
        });

        it('应该获取中文翻译', () => {
            const text = I18n.t('app.title');
            expect(text).toBe('智能不确定性驱动空间决策平台');
        });

        it('应该获取英文翻译', () => {
            I18n.setLocale('en-US');
            const text = I18n.t('app.title');
            expect(text).toBe('Uncertainty-Driven Adaptive Kriging Engine');
        });

        it('应该支持插值变量替换', () => {
            const text = I18n.t('upload.success', { count: 100 });
            expect(text).toBe('数据导入成功！点数: 100');
        });

        it('应该支持多个插值变量', () => {
            const text = I18n.t('export.downloading', { filename: 'result.csv' });
            expect(text).toBe('正在下载 result.csv...');
        });

        it('对于不存在的key应该返回key本身', () => {
            const text = I18n.t('nonexistent.key');
            expect(text).toBe('nonexistent.key');
        });

        it('插值时应该处理数字参数', () => {
            const text = I18n.t('feedback.stats', { count: 5 });
            expect(text).toBe('已提交 5 条反馈');
        });

        it('插值时应该处理字符串参数', () => {
            const text = I18n.t('export.done', { filename: 'data.csv' });
            expect(text).toBe('data.csv 下载完成');
        });
    });

    describe('可用语言列表', () => {
        it('应该返回正确的可用语言列表', () => {
            const locales = I18n.getAvailableLocales();
            expect(locales.map(item => item.code)).toEqual([
                'zh-CN',
                'en-US',
                'zh-TW',
                'ja-JP',
                'ko-KR'
            ]);
        });

        it('语言列表应该包含code和name属性', () => {
            const locales = I18n.getAvailableLocales();
            locales.forEach(locale => {
                expect(locale).toHaveProperty('code');
                expect(locale).toHaveProperty('name');
                expect(typeof locale.code).toBe('string');
                expect(typeof locale.name).toBe('string');
            });
        });
    });

    describe('懒加载语言包', () => {
        it('应该异步切换到 zh-TW', async () => {
            I18n.init('zh-CN');
            const changed = await I18n.setLocaleAsync('zh-TW');
            expect(changed).toBe(true);
            expect(I18n.locale).toBe('zh-TW');
            expect(I18n.t('settings.language.zh-TW')).toBe('繁體中文');
        });
    });

    describe('语言变化监听器', () => {
        beforeEach(() => {
            I18n.init();
        });

        it('应该能够注册语言变化监听器', () => {
            const callback = vi.fn();
            const remove = I18n.onChange(callback);
            
            expect(typeof remove).toBe('function');
        });

        it('语言变化时应该调用所有监听器', () => {
            const callback1 = vi.fn();
            const callback2 = vi.fn();
            
            I18n.onChange(callback1);
            I18n.onChange(callback2);
            
            I18n.setLocale('en-US');
            
            expect(callback1).toHaveBeenCalledWith('en-US');
            expect(callback2).toHaveBeenCalledWith('en-US');
        });

        it('应该能够移除监听器', () => {
            const callback = vi.fn();
            const remove = I18n.onChange(callback);
            
            remove();
            I18n.setLocale('en-US');
            
            expect(callback).not.toHaveBeenCalled();
        });

        it('监听器抛出错误时不应该影响其他监听器', () => {
            const errorCallback = vi.fn(() => { throw new Error('Test error'); });
            const normalCallback = vi.fn();
            
            I18n.onChange(errorCallback);
            I18n.onChange(normalCallback);
            
            // 应该不抛出错误
            expect(() => I18n.setLocale('en-US')).not.toThrow();
            
            expect(errorCallback).toHaveBeenCalled();
            expect(normalCallback).toHaveBeenCalled();
        });
    });

    describe('自定义语言包注册', () => {
        it('应该能够注册新的语言包', () => {
            const customMessages = {
                'custom.key': '自定义翻译'
            };
            
            I18n.registerLocale('custom', customMessages);
            
            // 切换到自定义语言
            I18n.setLocale('custom');
            expect(I18n.t('custom.key')).toBe('自定义翻译');
        });

        it('应该能够扩展现有语言包', () => {
            I18n.init('zh-CN');
            const extraMessages = {
                'new.key': '新的翻译'
            };
            
            I18n.registerLocale('zh-CN', extraMessages);
            
            expect(I18n.t('app.title')).toBe('智能不确定性驱动空间决策平台');
            expect(I18n.t('new.key')).toBe('新的翻译');
        });

        it('注册的语言包应该合并而不是覆盖', () => {
            I18n.init('zh-CN');
            const extraMessages = {
                'extra.key': '额外翻译'
            };
            
            I18n.registerLocale('zh-CN', extraMessages);
            
            // 原有的翻译应该仍然可用
            expect(I18n.t('app.title')).toBe('智能不确定性驱动空间决策平台');
            // 新增的翻译应该可用
            expect(I18n.t('extra.key')).toBe('额外翻译');
        });
    });

    describe('关键翻译完整性', () => {
        it('中文语言包应该包含所有必需的翻译', () => {
            const requiredKeys = [
                'app.title',
                'nav.newProject',
                'upload.title',
                'kriging.title',
                'task.title',
                'export.title',
                'layer.title',
                'common.confirm',
                'common.cancel'
            ];
            
            I18n.init('zh-CN');
            
            requiredKeys.forEach(key => {
                const translation = I18n.t(key);
                expect(translation).not.toBe(key);
                expect(translation).toBeTruthy();
            });
        });

        it('英文语言包应该包含所有必需的翻译', () => {
            const requiredKeys = [
                'app.title',
                'nav.newProject',
                'upload.title',
                'kriging.title',
                'task.title',
                'export.title',
                'layer.title',
                'common.confirm',
                'common.cancel'
            ];
            
            I18n.init('en-US');
            
            requiredKeys.forEach(key => {
                const translation = I18n.t(key);
                expect(translation).not.toBe(key);
                expect(translation).toBeTruthy();
            });
        });

        it('错误命名空间应支持中英文', () => {
            const errorKeys = [
                'error.network_error.message',
                'error.network_error.suggestion',
                'error.validation.geojson_missing_type',
                'error.common.retryButton'
            ];

            I18n.init('zh-CN');
            errorKeys.forEach(key => {
                expect(I18n.t(key)).not.toBe(key);
            });

            I18n.setLocale('en-US');
            errorKeys.forEach(key => {
                expect(I18n.t(key)).not.toBe(key);
            });
        });
    });

    describe('边界情况', () => {
        beforeEach(() => {
            I18n.init();
        });

        it('空参数插值应该正常工作', () => {
            const text = I18n.t('app.title', {});
            expect(text).toBe('智能不确定性驱动空间决策平台');
        });

        it('未匹配的插值变量应该保持原样', () => {
            const text = I18n.t('upload.success', { unmatched: 'value' });
            expect(text).toBe('数据导入成功！点数: {count}');
        });

        it('空字符串key应该返回空字符串', () => {
            const text = I18n.t('');
            expect(text).toBe('');
        });

        it('多次切换语言应该正常工作', () => {
            I18n.setLocale('en-US');
            expect(I18n.locale).toBe('en-US');
            
            I18n.setLocale('zh-CN');
            expect(I18n.locale).toBe('zh-CN');
            
            I18n.setLocale('en-US');
            expect(I18n.locale).toBe('en-US');
        });

        it('应能够计算语言覆盖率', () => {
            const coverage = I18n.getLocaleCoverage('en-US');
            expect(coverage).toBeGreaterThan(0.8);
            expect(coverage).toBeLessThanOrEqual(1);
        });

        it('应统计缺失翻译键的访问情况', () => {
            I18n.clearMissingKeyUsage();
            I18n.t('nonexistent.translation.key');
            I18n.t('nonexistent.translation.key');
            const usage = I18n.getMissingKeyUsage();
            expect(usage.length).toBeGreaterThan(0);
            expect(usage[0].key).toBe('nonexistent.translation.key');
            expect(usage[0].count).toBe(2);
        });

        it('应支持复数翻译', () => {
            I18n.init('en-US');
            expect(I18n.tp('common.items', 1)).toBe('1 item');
            expect(I18n.tp('common.items', 5)).toBe('5 items');
        });

        it('应支持数字和货币格式化', () => {
            I18n.init('en-US');
            const numberText = I18n.formatNumber(12345.67);
            const currencyText = I18n.formatCurrency(12345.67, 'USD');
            expect(numberText).toContain('12');
            expect(currencyText).toContain('$');
        });

        it('应支持日期时间格式化和时区设置', () => {
            I18n.init('zh-CN');
            I18n.setTimeZone('Asia/Shanghai');
            const result = I18n.formatDateTime('2026-03-26T08:00:00Z');
            expect(result).toBeTruthy();
        });

        it('应支持本地化排序', () => {
            I18n.init('zh-CN');
            const sorted = I18n.sortByLocale(['zeta', 'alpha', 'beta']);
            expect(sorted[0]).toBe('alpha');
        });
    });
});
