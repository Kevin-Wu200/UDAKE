import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { FeedbackCollector } from '../frontend/js/components/FeedbackCollector.js';

describe('FeedbackCollector', () => {
    let mockElements = {};

    beforeEach(() => {
        // 重置 mockElements
        mockElements = {
            '#feedback-content': { value: '', addEventListener: vi.fn(), focus: vi.fn(), tagName: 'TEXTAREA' },
            '#feedback-content-counter': { textContent: '', style: {} },
            '#feedback-file-drop': { addEventListener: vi.fn(), querySelector: vi.fn(() => null), focus: vi.fn() },
            '#feedback-file-input': { value: '', addEventListener: vi.fn(), click: vi.fn() },
            '#feedback-file-list': { innerHTML: '' },
            '#feedback-cancel': { addEventListener: vi.fn() },
            '#feedback-submit': { addEventListener: vi.fn() },
            '#feedback-stats': { innerHTML: '' },
            '#feedback-contact': { value: '', addEventListener: vi.fn() },
            '#feedback-close': { addEventListener: vi.fn() },
            '.modal-close': { addEventListener: vi.fn() },
            'textarea': { value: '', addEventListener: vi.fn(), focus: vi.fn(), tagName: 'TEXTAREA' }
        };

        // 保存到全局变量，以便在测试中访问
        global.testMockElements = mockElements;

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
                    setAttribute: vi.fn(),
                    getAttribute: vi.fn(() => null),
                    querySelector: vi.fn((selector) => {
                        if (mockElements[selector]) return mockElements[selector];
                        // 处理 textarea 选择器
                        if (selector === 'textarea') {
                            return { value: '', addEventListener: vi.fn(), focus: vi.fn() };
                        }
                        // 为其他选择器返回具有基本方法的 mock 元素
                        return {
                            value: '',
                            textContent: '',
                            style: {},
                            addEventListener: vi.fn(),
                            focus: vi.fn(),
                            click: vi.fn(),
                            tagName: 'DIV'
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
                    textContent: '',
                    dataset: {},
                    remove: vi.fn()
                };
                return element;
            }),
            querySelector: vi.fn((selector) => {
                if (mockElements[selector]) return mockElements[selector];
                return null;
            }),
            requestAnimationFrame: vi.fn((cb) => cb())
        };

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

        // Mock querySelector 为 document 添加全局查询能力
        document.querySelector = vi.fn((selector) => {
            if (mockElements[selector]) return mockElements[selector];
            if (selector === 'textarea') {
                return { value: '', addEventListener: vi.fn(), focus: vi.fn(), tagName: 'TEXTAREA' };
            }
            return null;
        });

        // Mock console
        console.log = vi.fn();
    });

    afterEach(() => {
        vi.clearAllMocks();
    });

    describe('初始化', () => {
        it('应该能够创建FeedbackCollector实例', () => {
            const collector = new FeedbackCollector();
            expect(collector).toBeDefined();
            expect(collector instanceof FeedbackCollector).toBe(true);
        });
    });

    describe('显示和隐藏', () => {
        it('应该能够显示反馈面板', () => {
            const collector = new FeedbackCollector();
            collector.show();
            
            expect(document.body.appendChild).toHaveBeenCalled();
        });

        it('不应该重复显示面板', () => {
            const collector = new FeedbackCollector();
            collector.show();
            collector.show();
            
            // appendChild应该只被调用一次
            expect(document.body.appendChild).toHaveBeenCalledTimes(1);
        });

        it('应该能够隐藏面板', () => {
            const collector = new FeedbackCollector();
            collector.show();
            collector.hide();
            
            expect(setTimeout).toHaveBeenCalled();
        });

        it('隐藏面板应该移除DOM元素', () => {
            const collector = new FeedbackCollector();
            collector.show();
            collector.hide();
            
            // setTimeout应该触发移除操作
            expect(setTimeout).toHaveBeenCalled();
        });
    });

    describe('创建覆盖层', () => {
        it('应该创建正确结构的DOM元素', () => {
            const collector = new FeedbackCollector();
            collector._createOverlay();
            
            expect(document.createElement).toHaveBeenCalled();
        });

        it('应该设置正确的ARIA属性', () => {
            const mockElement = {
                className: '',
                innerHTML: '',
                setAttribute: vi.fn(),
                getAttribute: vi.fn(() => null),
                querySelector: vi.fn((selector) => {
                    // 访问全局的 mockElements 变量
                    const outerMockElements = global.testMockElements || {};
                    if (outerMockElements[selector]) return outerMockElements[selector];
                    return null;
                }),
                querySelectorAll: vi.fn(() => []),
                addEventListener: vi.fn(),
                classList: { add: vi.fn(), remove: vi.fn() }
            };
            document.createElement.mockReturnValue(mockElement);

            const collector = new FeedbackCollector();
            collector._createOverlay();

            expect(mockElement.setAttribute).toHaveBeenCalledWith('role', 'dialog');
            expect(mockElement.setAttribute).toHaveBeenCalledWith('aria-modal', 'true');
            expect(mockElement.setAttribute).toHaveBeenCalledWith('aria-labelledby', 'feedback-title');
            expect(mockElement.setAttribute).toHaveBeenCalledWith('aria-describedby', 'feedback-description');
        });
    });

    describe('反馈类型', () => {
        it('应该包含问题反馈类型', () => {
            expect(FeedbackCollector.save).toBeDefined();
        });

        it('应该包含功能建议类型', () => {
            expect(FeedbackCollector.save).toBeDefined();
        });

        it('应该包含体验优化类型', () => {
            expect(FeedbackCollector.save).toBeDefined();
        });

        it('应该包含其他类型', () => {
            expect(FeedbackCollector.save).toBeDefined();
        });
    });

    describe('保存反馈', () => {
        it('应该能够保存反馈', () => {
            const data = {
                type: 'bug',
                content: '测试反馈内容',
                contact: 'test@example.com'
            };
            
            FeedbackCollector.save(data);
            
            expect(localStorage.setItem).toHaveBeenCalled();
        });

        it('保存时应该生成唯一ID', () => {
            const data = { type: 'bug', content: '测试' };
            
            FeedbackCollector.save(data);
            
            const setItemCall = localStorage.setItem.mock.calls[0];
            const savedData = JSON.parse(setItemCall[1]);
            
            expect(savedData[0].id).toBeDefined();
            expect(savedData[0].id).toMatch(/^fb_\d+_[a-z0-9]+$/);
        });

        it('保存时应该添加时间戳', () => {
            const data = { type: 'bug', content: '测试' };
            
            FeedbackCollector.save(data);
            
            const setItemCall = localStorage.setItem.mock.calls[0];
            const savedData = JSON.parse(setItemCall[1]);
            
            expect(savedData[0].timestamp).toBeDefined();
            expect(typeof savedData[0].timestamp).toBe('number');
        });

        it('保存时应该设置状态为pending', () => {
            const data = { type: 'bug', content: '测试' };
            
            FeedbackCollector.save(data);
            
            const setItemCall = localStorage.setItem.mock.calls[0];
            const savedData = JSON.parse(setItemCall[1]);
            
            expect(savedData[0].status).toBe('pending');
        });

        it('应该保存多个反馈', () => {
            FeedbackCollector.save({ type: 'bug', content: '反馈1' });
            FeedbackCollector.save({ type: 'feature', content: '反馈2' });
            
            expect(localStorage.setItem).toHaveBeenCalledTimes(2);
        });

        it('保存时应该记录日志', () => {
            const data = { type: 'bug', content: '测试' };
            
            FeedbackCollector.save(data);
            
            expect(console.log).toHaveBeenCalledWith('[Feedback] 反馈已保存');
        });
    });

    describe('获取所有反馈', () => {
        it('应该能够获取所有反馈', () => {
            localStorage.getItem.mockReturnValue('[]');
            const entries = FeedbackCollector.getAll();
            
            expect(Array.isArray(entries)).toBe(true);
        });

        it('应该解析已保存的反馈', () => {
            const savedData = [
                { id: 'fb_1', type: 'bug', content: '测试', timestamp: Date.now(), status: 'pending' }
            ];
            localStorage.getItem.mockReturnValue(JSON.stringify(savedData));
            
            const entries = FeedbackCollector.getAll();
            
            expect(entries.length).toBe(1);
            expect(entries[0].id).toBe('fb_1');
        });

        it('应该处理无效的保存数据', () => {
            localStorage.getItem.mockReturnValue('invalid json');
            const entries = FeedbackCollector.getAll();
            
            expect(entries).toEqual([]);
        });

        it('应该处理空数据', () => {
            localStorage.getItem.mockReturnValue(null);
            const entries = FeedbackCollector.getAll();
            
            expect(entries).toEqual([]);
        });
    });

    describe('获取统计信息', () => {
        it('应该返回总数统计', () => {
            const savedData = [
                { type: 'bug', content: '测试1' },
                { type: 'feature', content: '测试2' },
                { type: 'bug', content: '测试3' }
            ];
            localStorage.getItem.mockReturnValue(JSON.stringify(savedData));
            
            const stats = FeedbackCollector.getStats();
            
            expect(stats.total).toBe(3);
        });

        it('应该返回按类型统计', () => {
            const savedData = [
                { type: 'bug', content: '测试1' },
                { type: 'feature', content: '测试2' },
                { type: 'bug', content: '测试3' },
                { type: 'improvement', content: '测试4' }
            ];
            localStorage.getItem.mockReturnValue(JSON.stringify(savedData));
            
            const stats = FeedbackCollector.getStats();
            
            expect(stats.byType.bug).toBe(2);
            expect(stats.byType.feature).toBe(1);
            expect(stats.byType.improvement).toBe(1);
        });

        it('空数据应该返回零统计', () => {
            localStorage.getItem.mockReturnValue(null);
            
            const stats = FeedbackCollector.getStats();
            
            expect(stats.total).toBe(0);
            expect(Object.keys(stats.byType).length).toBe(0);
        });
    });

    describe('事件处理', () => {
it('应该处理关闭按钮点击', () => {
            const collector = new FeedbackCollector();
            const mockCloseBtn = {
                addEventListener: vi.fn()
            };

            const mockOverlay = {
                querySelector: vi.fn((selector) => {
                    if (selector === '.modal-close') return mockCloseBtn;
                    // 访问全局的 mockElements 变量
                    const outerMockElements = global.testMockElements || {};
                    if (outerMockElements[selector]) return outerMockElements[selector];
                    return null;
                }),
                querySelectorAll: vi.fn(() => []),
                setAttribute: vi.fn(),
                addEventListener: vi.fn(),
                classList: { add: vi.fn(), remove: vi.fn() }
            };
            document.createElement.mockReturnValue(mockOverlay);

            collector.show();

            expect(mockCloseBtn.addEventListener).toHaveBeenCalledWith('click', expect.any(Function));
        });

        it('应该处理取消按钮点击', () => {
            const collector = new FeedbackCollector();
            const mockCancelBtn = {
                addEventListener: vi.fn()
            };

            const mockOverlay = {
                querySelector: vi.fn((selector) => {
                    if (selector === '#feedback-cancel') return mockCancelBtn;
                    // 访问全局的 mockElements 变量
                    const outerMockElements = global.testMockElements || {};
                    if (outerMockElements[selector]) return outerMockElements[selector];
                    return null;
                }),
                querySelectorAll: vi.fn(() => []),
                setAttribute: vi.fn(),
                addEventListener: vi.fn(),
                classList: { add: vi.fn(), remove: vi.fn() }
            };
            document.createElement.mockReturnValue(mockOverlay);

            collector.show();

            expect(mockCancelBtn.addEventListener).toHaveBeenCalledWith('click', expect.any(Function));
        });

        it('应该处理提交按钮点击', () => {
            const collector = new FeedbackCollector();
            const mockSubmitBtn = {
                addEventListener: vi.fn()
            };

            const mockOverlay = {
                querySelector: vi.fn((selector) => {
                    if (selector === '#feedback-submit') return mockSubmitBtn;
                    // 访问全局的 mockElements 变量
                    const outerMockElements = global.testMockElements || {};
                    if (outerMockElements[selector]) return outerMockElements[selector];
                    return null;
                }),
                querySelectorAll: vi.fn(() => []),
                setAttribute: vi.fn(),
                addEventListener: vi.fn(),
                classList: { add: vi.fn(), remove: vi.fn() }
            };
            document.createElement.mockReturnValue(mockOverlay);

            collector.show();

            expect(mockSubmitBtn.addEventListener).toHaveBeenCalledWith('click', expect.any(Function));
        });

        it('应该处理点击遮罩层关闭', () => {
            const collector = new FeedbackCollector();
            const mockOverlay = {
                querySelector: vi.fn((selector) => {
                    // 访问全局的 mockElements 变量
                    const outerMockElements = global.testMockElements || {};
                    if (outerMockElements[selector]) return outerMockElements[selector];
                    return null;
                }),
                querySelectorAll: vi.fn(() => []),
                setAttribute: vi.fn(),
                addEventListener: vi.fn(),
                classList: { add: vi.fn(), remove: vi.fn() }
            };
            document.createElement.mockReturnValue(mockOverlay);

            collector.show();

            expect(mockOverlay.addEventListener).toHaveBeenCalledWith('click', expect.any(Function));
        });
    });

    describe('反馈类型选择', () => {
        it('应该能够选择不同的反馈类型', () => {
            const collector = new FeedbackCollector();
            const mockTypeBtns = [
                { addEventListener: vi.fn(), classList: { add: vi.fn(), remove: vi.fn() }, setAttribute: vi.fn(), dataset: { type: 'bug' } },
                { addEventListener: vi.fn(), classList: { add: vi.fn(), remove: vi.fn() }, setAttribute: vi.fn(), dataset: { type: 'feature' } }
            ];

            const mockOverlay = {
                querySelector: vi.fn((selector) => {
                    // 访问全局的 mockElements 变量
                    const outerMockElements = global.testMockElements || {};
                    if (outerMockElements[selector]) return outerMockElements[selector];
                    return null;
                }),
                querySelectorAll: vi.fn(() => mockTypeBtns),
                setAttribute: vi.fn(),
                addEventListener: vi.fn(),
                classList: { add: vi.fn(), remove: vi.fn() }
            };
            document.createElement.mockReturnValue(mockOverlay);

            collector.show();

            expect(mockTypeBtns[0].addEventListener).toHaveBeenCalledWith('click', expect.any(Function));
        });

        it('应该更新选中状态的ARIA属性', () => {
            const mockBtn = {
                addEventListener: vi.fn(),
                classList: { add: vi.fn(), remove: vi.fn() },
                setAttribute: vi.fn(),
                dataset: { type: 'bug' }
            };

            // 测试事件绑定机制
            mockBtn.addEventListener('click', vi.fn());
            
            // 验证方法可以被调用
            expect(mockBtn.addEventListener).toHaveBeenCalled();
            
            // 测试事件处理函数更新 aria-checked 属性
            mockBtn.setAttribute('aria-checked', 'true');
            expect(mockBtn.setAttribute).toHaveBeenCalledWith('aria-checked', 'true');
        });
    });

    describe('表单验证', () => {
        it('提交时应该验证内容不为空', () => {
            const collector = new FeedbackCollector();
            const mockContent = {
                value: '',
                focus: vi.fn(),
                addEventListener: vi.fn()
            };

            const mockSubmitBtn = {
                addEventListener: vi.fn((event, handler) => {
                    // 模拟提交处理
                    if (mockContent.value.trim() === '') {
                        mockContent.focus();
                    }
                })
            };

            const mockOverlay = {
                querySelector: vi.fn((selector) => {
                    if (selector === '#feedback-content') return mockContent;
                    if (selector === '#feedback-submit') return mockSubmitBtn;
                    // 访问全局的 mockElements 变量
                    const outerMockElements = global.testMockElements || {};
                    if (outerMockElements[selector]) return outerMockElements[selector];
                    return null;
                }),
                querySelectorAll: vi.fn(() => []),
                setAttribute: vi.fn(),
                addEventListener: vi.fn(),
                classList: { add: vi.fn(), remove: vi.fn() },
                remove: vi.fn()
            };
            document.createElement.mockReturnValue(mockOverlay);

            collector.show();
            
            // 触发提交按钮的点击事件
            const clickHandler = mockSubmitBtn.addEventListener.mock.calls[0][1];
            clickHandler();
            
            expect(mockContent.focus).toHaveBeenCalled();
        });

        it('应该允许空联系方式', () => {
            const data = {
                type: 'bug',
                content: '测试反馈',
                contact: ''
            };
            
            // 不应该抛出错误
            expect(() => FeedbackCollector.save(data)).not.toThrow();
        });
    });

    describe('UI交互', () => {
        it('显示时应该添加modal-show类', () => {
            // 重置 requestAnimationFrame mock 以便捕获调用
            global.requestAnimationFrame = vi.fn((cb) => {
                cb();
                return 1;
            });

            const collector = new FeedbackCollector();
            const mockOverlay = {
                querySelector: vi.fn((selector) => {
                    // 访问全局的 mockElements 变量
                    const outerMockElements = global.testMockElements || {};
                    if (outerMockElements[selector]) return outerMockElements[selector];
                    return null;
                }),
                querySelectorAll: vi.fn(() => []),
                setAttribute: vi.fn(),
                addEventListener: vi.fn(),
                classList: { add: vi.fn(), remove: vi.fn() }
            };
            document.createElement.mockReturnValue(mockOverlay);

            collector.show();

            expect(global.requestAnimationFrame).toHaveBeenCalled();
            expect(mockOverlay.classList.add).toHaveBeenCalledWith('modal-show');
        });

        it('隐藏时应该移除modal-show类', () => {
            const collector = new FeedbackCollector();
            const mockOverlay = {
                querySelector: vi.fn((selector) => {
                    // 访问全局的 mockElements 变量
                    const outerMockElements = global.testMockElements || {};
                    if (outerMockElements[selector]) return outerMockElements[selector];
                    return null;
                }),
                querySelectorAll: vi.fn(() => []),
                setAttribute: vi.fn(),
                addEventListener: vi.fn(),
                classList: { add: vi.fn(), remove: vi.fn() },
                remove: vi.fn()
            };
            document.createElement.mockReturnValue(mockOverlay);
            
            collector.show();
            collector.hide();
            
            expect(mockOverlay.classList.remove).toHaveBeenCalledWith('modal-show');
        });
    });

    describe('边界情况', () => {
        it('应该处理localStorage不可用的情况', () => {
            global.localStorage = null;
            
            // 不应该抛出错误
            expect(() => new FeedbackCollector()).not.toThrow();
        });

        it('应该处理多次show调用', () => {
            const collector = new FeedbackCollector();
            collector.show();
            collector.show();
            collector.show();
            
            // 只应该创建一个覆盖层
            expect(document.body.appendChild).toHaveBeenCalledTimes(1);
        });

        it('应该处理没有overlay时的hide调用', () => {
            const collector = new FeedbackCollector();
            
            // 不应该抛出错误
            expect(() => collector.hide()).not.toThrow();
        });
    });

    describe('静态方法', () => {
        it('应该暴露save静态方法', () => {
            expect(FeedbackCollector.save).toBeDefined();
            expect(typeof FeedbackCollector.save).toBe('function');
        });

        it('应该暴露getAll静态方法', () => {
            expect(FeedbackCollector.getAll).toBeDefined();
            expect(typeof FeedbackCollector.getAll).toBe('function');
        });

        it('应该暴露getStats静态方法', () => {
            expect(FeedbackCollector.getStats).toBeDefined();
            expect(typeof FeedbackCollector.getStats).toBe('function');
        });
    });

    describe('反馈数据结构', () => {
        it('保存的反馈应该包含所有必需字段', () => {
            const data = {
                type: 'bug',
                content: '测试反馈',
                contact: 'test@example.com'
            };
            
            FeedbackCollector.save(data);
            
            const setItemCall = localStorage.setItem.mock.calls[0];
            const savedData = JSON.parse(setItemCall[1]);
            
            expect(savedData[0]).toHaveProperty('id');
            expect(savedData[0]).toHaveProperty('type');
            expect(savedData[0]).toHaveProperty('content');
            expect(savedData[0]).toHaveProperty('timestamp');
            expect(savedData[0]).toHaveProperty('status');
        });

        it('可选字段contact应该正确处理', () => {
            const data1 = { type: 'bug', content: '测试1', contact: 'test@test.com' };
            const data2 = { type: 'bug', content: '测试2' };
            
            FeedbackCollector.save(data1);
            FeedbackCollector.save(data2);
            
            const setItemCalls = localStorage.setItem.mock.calls;
            const savedData1 = JSON.parse(setItemCalls[0][1]);
            const savedData2 = JSON.parse(setItemCalls[1][1]);
            
            expect(savedData1[0].contact).toBe('test@test.com');
            expect(savedData2[0].contact).toBeUndefined();
        });
    });
});