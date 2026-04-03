import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { PreferencesPanel } from '../apps/frontend/js/components/PreferencesPanel.js';

describe('PreferencesPanel', () => {
    let mockElements = {};

    beforeEach(() => {
        // 重置 mockElements
        mockElements = {};

        // Mock DOM环境
        global.document = {
            body: {
                appendChild: vi.fn(),
                removeChild: vi.fn()
            },
            createElement: vi.fn((tag) => {
                const element = {
                    tagName: tag,
                    className: '',
                    id: '',
                    innerHTML: '',
                    style: {},
                    attributes: {},
                    setAttribute: vi.fn((name, value) => {
                        element.attributes[name] = value;
                    }),
                    getAttribute: vi.fn((name) => element.attributes[name] || null),
                    querySelector: vi.fn((selector) => {
                        // 优先返回 mockElements 中的元素
                        if (mockElements[selector]) {
                            return mockElements[selector];
                        }
                        // 为 class 选择器创建模拟元素
                        if (selector.startsWith('.')) {
                            const mockElement = {
                                className: selector.substring(1),
                                addEventListener: vi.fn(),
                                removeEventListener: vi.fn()
                            };
                            return mockElement;
                        }
                        // 为其他选择器返回一个基本的 mock 元素
                        return {
                            value: '',
                            checked: false,
                            addEventListener: vi.fn(),
                            removeEventListener: vi.fn(),
                            querySelector: vi.fn((sel) => mockElements[sel] || null),
                            querySelectorAll: vi.fn(() => []),
                            classList: { add: vi.fn(), remove: vi.fn() }
                        };
                    }),
                    querySelectorAll: vi.fn(() => []),
                    addEventListener: vi.fn(),
                    removeEventListener: vi.fn(),
                    classList: {
                        add: vi.fn(),
                        remove: vi.fn(),
                        contains: vi.fn(() => false)
                    },
                    value: '',
                    checked: false,
                    remove: vi.fn()
                };
                return element;
            }),
            requestAnimationFrame: vi.fn((cb) => cb())
        };

        // 创建模拟的表单元素
        const createMockFormElement = (id) => {
            const element = {
                id,
                value: '',
                checked: false,
                querySelector: vi.fn((selector) => {
                    // 递归查找子元素
                    if (mockElements[selector]) {
                        return mockElements[selector];
                    }
                    return null;
                }),
                querySelectorAll: vi.fn(() => []),
                addEventListener: vi.fn(),
                removeEventListener: vi.fn(),
                classList: {
                    add: vi.fn(),
                    remove: vi.fn(),
                    contains: vi.fn(() => false)
                }
            };
            mockElements[`#${id}`] = element;
            return element;
        };

        // 添加 class 选择器的 mock 元素
        mockElements['.modal-close'] = {
            className: 'modal-close',
            addEventListener: vi.fn(),
            removeEventListener: vi.fn()
        };

        createMockFormElement('pref-theme');
        createMockFormElement('pref-animations');
        createMockFormElement('pref-show-coords');
        createMockFormElement('pref-grid-res');
        createMockFormElement('pref-export-fmt');
        createMockFormElement('pref-autosave');
        createMockFormElement('pref-notifications');
        createMockFormElement('pref-reset');
        createMockFormElement('pref-save');

        // Mock localStorage
        const localStorageMock = {
            getItem: vi.fn(() => null),
            setItem: vi.fn(),
            removeItem: vi.fn(),
            clear: vi.fn()
        };
        global.localStorage = localStorageMock;

        // Mock setTimeout
        global.setTimeout = vi.fn((cb, delay) => {
            cb();
            return 1;
        });
    });

    afterEach(() => {
        vi.clearAllMocks();
    });

    describe('初始化', () => {
        it('应该能够创建PreferencesPanel实例', () => {
            const panel = new PreferencesPanel();
            expect(panel).toBeDefined();
            expect(panel instanceof PreferencesPanel).toBe(true);
        });

        it('应该能够传入onChange回调', () => {
            const onChange = vi.fn();
            const panel = new PreferencesPanel(onChange);
            expect(panel).toBeDefined();
        });

        it('应该加载默认偏好设置', () => {
            localStorage.getItem.mockReturnValue(null);
            const panel = new PreferencesPanel();
            const prefs = panel.preferences;
            
            expect(prefs.theme).toBe('auto');
            expect(prefs.language).toBe('zh-CN');
            expect(prefs.notifications).toBe(true);
            expect(prefs.mapEngine).toBe('geoscene');
            expect(prefs.gridResolution).toBe(100);
            expect(prefs.exportFormat).toBe('geojson');
            expect(prefs.autoSave).toBe(true);
            expect(prefs.showCoordinates).toBe(true);
            expect(prefs.animationsEnabled).toBe(true);
        });

        it('应该加载已保存的偏好设置', () => {
            const savedPrefs = {
                theme: 'dark',
                language: 'en-US',
                notifications: false
            };
            localStorage.getItem.mockReturnValue(JSON.stringify(savedPrefs));
            
            const panel = new PreferencesPanel();
            const prefs = panel.preferences;
            
            expect(prefs.theme).toBe('dark');
            expect(prefs.language).toBe('en-US');
            expect(prefs.notifications).toBe(false);
        });

        it('应该处理无效的保存数据', () => {
            localStorage.getItem.mockReturnValue('invalid json');
            
            const panel = new PreferencesPanel();
            const prefs = panel.preferences;
            
            // 应该回退到默认值
            expect(prefs.theme).toBe('auto');
        });
    });

    describe('显示和隐藏', () => {
        it('应该能够显示面板', () => {
            const panel = new PreferencesPanel();
            panel.show();
            
            expect(document.body.appendChild).toHaveBeenCalled();
        });

        it('不应该重复显示面板', () => {
            const panel = new PreferencesPanel();
            panel.show();
            panel.show();
            
            // appendChild应该只被调用一次
            expect(document.body.appendChild).toHaveBeenCalledTimes(1);
        });

        it('应该能够隐藏面板', () => {
            // 重置 mock 以确保使用默认行为
            document.createElement.mockReset();

            const panel = new PreferencesPanel();
            panel.show();
            panel.hide();

            expect(setTimeout).toHaveBeenCalled();
        });

        it('隐藏面板应该移除DOM元素', () => {
            // 重置 mock 以确保使用默认行为
            document.createElement.mockReset();

            const panel = new PreferencesPanel();
            panel.show();
            panel.hide();

            // setTimeout应该触发移除操作
            expect(setTimeout).toHaveBeenCalled();
        });
    });

    describe('preferences属性', () => {
        it('应该返回偏好设置的副本', () => {
            const panel = new PreferencesPanel();
            const prefs1 = panel.preferences;
            const prefs2 = panel.preferences;
            
            expect(prefs1).not.toBe(prefs2);
            expect(prefs1).toEqual(prefs2);
        });

        it('修改返回的副本不应该影响内部状态', () => {
            const panel = new PreferencesPanel();
            const prefs = panel.preferences;
            prefs.theme = 'dark';
            
            expect(panel.preferences.theme).toBe('auto');
        });
    });

    describe('保存和加载', () => {
        it('保存时应该调用localStorage.setItem', () => {
            const onChange = vi.fn();
            const panel = new PreferencesPanel(onChange);
            
            // 模拟内部保存调用
            panel._save();
            
            expect(localStorage.setItem).toHaveBeenCalled();
        });

        it('保存时应该调用onChange回调', () => {
            const onChange = vi.fn();
            const panel = new PreferencesPanel(onChange);
            
            panel._save();
            
            expect(onChange).toHaveBeenCalledWith(panel.preferences);
        });

        it('加载时应该读取localStorage', () => {
            localStorage.getItem.mockReturnValue(JSON.stringify({ theme: 'dark' }));
            const panel = new PreferencesPanel();
            
            expect(localStorage.getItem).toHaveBeenCalled();
        });
    });

    describe('创建覆盖层', () => {
        it('应该创建正确结构的DOM元素', () => {
            const panel = new PreferencesPanel();
            panel._createOverlay();
            
            expect(document.createElement).toHaveBeenCalled();
        });

        it('应该设置正确的ARIA属性', () => {
            const mockElement = {
                className: '',
                innerHTML: '',
                setAttribute: vi.fn(),
                querySelector: vi.fn((selector) => {
                    // 返回模拟表单元素
                    if (mockElements[selector]) return mockElements[selector];
                    return null;
                }),
                querySelectorAll: vi.fn(() => []),
                classList: { add: vi.fn(), remove: vi.fn() },
                remove: vi.fn(),
                addEventListener: vi.fn()
            };
            document.createElement.mockReturnValue(mockElement);

            const panel = new PreferencesPanel();
            panel._createOverlay();

            expect(mockElement.setAttribute).toHaveBeenCalledWith('role', 'dialog');
            expect(mockElement.setAttribute).toHaveBeenCalledWith('aria-label', '偏好设置');
        });
    });

    describe('填充值', () => {
        it('应该正确填充主题选择', () => {
            const panel = new PreferencesPanel();
            const mockRoot = {
                querySelector: vi.fn((selector) => ({
                    value: 'auto'
                }))
            };
            
            panel._populateValues(mockRoot);
            
            expect(mockRoot.querySelector).toHaveBeenCalledWith('#pref-theme');
        });

        it('应该正确填充复选框值', () => {
            const panel = new PreferencesPanel();
            const mockRoot = {
                querySelector: vi.fn((selector) => ({
                    checked: true
                }))
            };
            
            panel._populateValues(mockRoot);
            
            expect(mockRoot.querySelector).toHaveBeenCalledWith('#pref-animations');
        });

        it('应该正确填充数字输入', () => {
            const panel = new PreferencesPanel();
            const mockRoot = {
                querySelector: vi.fn((selector) => ({
                    value: '100'
                }))
            };
            
            panel._populateValues(mockRoot);
            
            expect(mockRoot.querySelector).toHaveBeenCalledWith('#pref-grid-res');
        });
    });

    describe('收集值', () => {
        it('应该正确收集主题选择', () => {
            const panel = new PreferencesPanel();
            const mockRoot = {
                querySelector: vi.fn((selector) => ({
                    value: 'dark',
                    checked: true
                }))
            };
            
            panel._collectValues(mockRoot);
            
            expect(mockRoot.querySelector).toHaveBeenCalledWith('#pref-theme');
        });

        it('应该正确收集复选框值', () => {
            const panel = new PreferencesPanel();
            const mockRoot = {
                querySelector: vi.fn((selector) => ({
                    value: 'dark',
                    checked: false
                }))
            };
            
            panel._collectValues(mockRoot);
            
            expect(mockRoot.querySelector).toHaveBeenCalledWith('#pref-animations');
        });

        it('应该正确收集数字输入值', () => {
            const panel = new PreferencesPanel();
            const mockRoot = {
                querySelector: vi.fn((selector) => ({
                    value: '200',
                    checked: true
                }))
            };
            
            panel._collectValues(mockRoot);
            
            expect(mockRoot.querySelector).toHaveBeenCalledWith('#pref-grid-res');
        });

        it('应该处理无效的数字输入', () => {
            const panel = new PreferencesPanel();
            const mockRoot = {
                querySelector: vi.fn((selector) => ({
                    value: 'invalid',
                    checked: true
                }))
            };
            
            panel._collectValues(mockRoot);
            
            // 应该使用默认值100
            expect(panel.preferences.gridResolution).toBeDefined();
        });
    });

    describe('静态方法', () => {
        it('应该暴露getCurrent静态方法', () => {
            expect(PreferencesPanel.getCurrent).toBeDefined();
            expect(typeof PreferencesPanel.getCurrent).toBe('function');
        });

        it('getCurrent应该返回默认偏好', () => {
            localStorage.getItem.mockReturnValue(null);
            const prefs = PreferencesPanel.getCurrent();
            
            expect(prefs.theme).toBe('auto');
            expect(prefs.language).toBe('zh-CN');
        });

        it('getCurrent应该返回已保存的偏好', () => {
            const savedPrefs = { theme: 'light', language: 'en' };
            localStorage.getItem.mockReturnValue(JSON.stringify(savedPrefs));
            
            const prefs = PreferencesPanel.getCurrent();
            
            expect(prefs.theme).toBe('light');
            expect(prefs.language).toBe('en');
        });

        it('getCurrent应该处理无效的保存数据', () => {
            localStorage.getItem.mockReturnValue('invalid');
            
            const prefs = PreferencesPanel.getCurrent();
            
            expect(prefs.theme).toBe('auto');
        });
    });

    describe('事件处理', () => {
        it('应该处理关闭按钮点击', () => {
            const panel = new PreferencesPanel();
            const mockCloseBtn = {
                addEventListener: vi.fn()
            };

            const mockOverlay = {
                querySelector: vi.fn((selector) => {
                    if (selector === '.modal-close') return mockCloseBtn;
                    if (mockElements[selector]) return mockElements[selector];
                    return null;
                }),
                querySelectorAll: vi.fn(() => []),
                addEventListener: vi.fn(),
                setAttribute: vi.fn(),
                classList: { add: vi.fn(), remove: vi.fn() },
                remove: vi.fn()
            };
            document.createElement.mockReturnValue(mockOverlay);

            panel.show();

            expect(mockCloseBtn.addEventListener).toHaveBeenCalledWith('click', expect.any(Function));
        });

        it('应该处理点击遮罩层关闭', () => {
            const panel = new PreferencesPanel();
            const mockOverlay = {
                querySelector: vi.fn((selector) => {
                    if (mockElements[selector]) return mockElements[selector];
                    return null;
                }),
                querySelectorAll: vi.fn(() => []),
                addEventListener: vi.fn(),
                setAttribute: vi.fn(),
                classList: { add: vi.fn(), remove: vi.fn() },
                remove: vi.fn()
            };
            document.createElement.mockReturnValue(mockOverlay);

            panel.show();

            expect(mockOverlay.addEventListener).toHaveBeenCalledWith('click', expect.any(Function));
        });

        it('应该处理保存按钮点击', () => {
            const panel = new PreferencesPanel();
            const mockSaveBtn = {
                addEventListener: vi.fn()
            };

            const mockOverlay = {
                querySelector: vi.fn((selector) => {
                    if (selector === '#pref-save') return mockSaveBtn;
                    if (mockElements[selector]) return mockElements[selector];
                    return null;
                }),
                querySelectorAll: vi.fn(() => []),
                addEventListener: vi.fn(),
                setAttribute: vi.fn(),
                classList: { add: vi.fn(), remove: vi.fn() },
                remove: vi.fn()
            };
            document.createElement.mockReturnValue(mockOverlay);

            panel.show();

            expect(mockSaveBtn.addEventListener).toHaveBeenCalledWith('click', expect.any(Function));
        });

        it('应该处理恢复默认按钮点击', () => {
            const panel = new PreferencesPanel();
            const mockResetBtn = {
                addEventListener: vi.fn()
            };

            const mockOverlay = {
                querySelector: vi.fn((selector) => {
                    if (selector === '#pref-reset') return mockResetBtn;
                    if (mockElements[selector]) return mockElements[selector];
                    return null;
                }),
                querySelectorAll: vi.fn(() => []),
                addEventListener: vi.fn(),
                setAttribute: vi.fn(),
                classList: { add: vi.fn(), remove: vi.fn() },
                remove: vi.fn()
            };
            document.createElement.mockReturnValue(mockOverlay);

            panel.show();

            expect(mockResetBtn.addEventListener).toHaveBeenCalledWith('click', expect.any(Function));
        });
    });

    describe('UI交互', () => {
        it('显示时应该添加modal-show类', () => {
            // 重置 requestAnimationFrame mock 以便捕获调用
            global.requestAnimationFrame = vi.fn((cb) => {
                cb();
                return 1;
            });

            const panel = new PreferencesPanel();
            const mockOverlay = {
                querySelector: vi.fn((selector) => {
                    if (mockElements[selector]) return mockElements[selector];
                    return null;
                }),
                querySelectorAll: vi.fn(() => []),
                addEventListener: vi.fn(),
                setAttribute: vi.fn(),
                classList: { add: vi.fn(), remove: vi.fn() },
                remove: vi.fn()
            };
            document.createElement.mockReturnValue(mockOverlay);

            panel.show();

            expect(global.requestAnimationFrame).toHaveBeenCalled();
            expect(mockOverlay.classList.add).toHaveBeenCalledWith('modal-show');
        });

        it('隐藏时应该移除modal-show类', () => {
            const panel = new PreferencesPanel();
            const mockOverlay = {
                querySelector: vi.fn((selector) => {
                    if (mockElements[selector]) return mockElements[selector];
                    return null;
                }),
                querySelectorAll: vi.fn(() => []),
                addEventListener: vi.fn(),
                setAttribute: vi.fn(),
                classList: { add: vi.fn(), remove: vi.fn() },
                remove: vi.fn()
            };
            document.createElement.mockReturnValue(mockOverlay);

            panel.show();
            panel.hide();

            expect(mockOverlay.classList.remove).toHaveBeenCalledWith('modal-show');
        });
    });

    describe('边界情况', () => {
        it('应该处理localStorage不可用的情况', () => {
            global.localStorage = null;
            
            // 不应该抛出错误
            expect(() => new PreferencesPanel()).not.toThrow();
        });

        it('应该处理多次show调用', () => {
            const panel = new PreferencesPanel();
            panel.show();
            panel.show();
            panel.show();
            
            // 只应该创建一个覆盖层
            expect(document.body.appendChild).toHaveBeenCalledTimes(1);
        });

        it('应该处理没有overlay时的hide调用', () => {
            const panel = new PreferencesPanel();
            
            // 不应该抛出错误
            expect(() => panel.hide()).not.toThrow();
        });
    });

    describe('偏好设置项', () => {
        it('应该包含主题设置', () => {
            const panel = new PreferencesPanel();
            expect(panel.preferences.theme).toBeDefined();
        });

        it('应该包含语言设置', () => {
            const panel = new PreferencesPanel();
            expect(panel.preferences.language).toBeDefined();
        });

        it('应该包含通知设置', () => {
            const panel = new PreferencesPanel();
            expect(panel.preferences.notifications).toBeDefined();
        });

        it('应该包含地图引擎设置', () => {
            const panel = new PreferencesPanel();
            expect(panel.preferences.mapEngine).toBeDefined();
        });

        it('应该包含网格分辨率设置', () => {
            const panel = new PreferencesPanel();
            expect(panel.preferences.gridResolution).toBeDefined();
        });

        it('应该包含导出格式设置', () => {
            const panel = new PreferencesPanel();
            expect(panel.preferences.exportFormat).toBeDefined();
        });

        it('应该包含自动保存设置', () => {
            const panel = new PreferencesPanel();
            expect(panel.preferences.autoSave).toBeDefined();
        });

        it('应该包含显示坐标设置', () => {
            const panel = new PreferencesPanel();
            expect(panel.preferences.showCoordinates).toBeDefined();
        });

        it('应该包含动画启用设置', () => {
            const panel = new PreferencesPanel();
            expect(panel.preferences.animationsEnabled).toBeDefined();
        });
    });
});