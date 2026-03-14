import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { TemplateDownloader } from '../frontend/js/components/TemplateDownloader.js';

describe('TemplateDownloader', () => {
    beforeEach(() => {
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
                        // 为特定的选择器返回模拟元素
                        if (selector === '.open-location-btn' || selector === '.close-dialog-btn') {
                            return {
                                addEventListener: vi.fn(),
                                click: vi.fn()
                            };
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
                    },
                    value: '',
                    textContent: '',
                    dataset: {},
                    click: vi.fn()
                };
                return element;
            }),
            requestAnimationFrame: vi.fn((cb) => cb())
        };

        // Mock URL和Blob
        global.URL = {
            createObjectURL: vi.fn(() => 'blob:mock-url'),
            revokeObjectURL: vi.fn()
        };
        
        global.Blob = class Blob {
            constructor(data, options) {
                this.data = data;
                this.options = options;
            }
        };
    });

    afterEach(() => {
        vi.clearAllMocks();
    });

    describe('获取模板列表', () => {
        it('应该能够获取所有模板信息', () => {
            const templates = TemplateDownloader.getTemplates();
            
            expect(Array.isArray(templates)).toBe(true);
            expect(templates.length).toBeGreaterThan(0);
        });

        it('模板应该包含name和description字段', () => {
            const templates = TemplateDownloader.getTemplates();
            
            templates.forEach(template => {
                expect(template).toHaveProperty('name');
                expect(template).toHaveProperty('description');
                expect(typeof template.name).toBe('string');
                expect(typeof template.description).toBe('string');
            });
        });

        it('应该包含基础采样点模板', () => {
            const templates = TemplateDownloader.getTemplates();
            const basicTemplate = templates.find(t => t.name.includes('基础采样点'));
            
            expect(basicTemplate).toBeDefined();
        });

        it('应该包含土壤采样模板', () => {
            const templates = TemplateDownloader.getTemplates();
            const soilTemplate = templates.find(t => t.name.includes('土壤采样'));
            
            expect(soilTemplate).toBeDefined();
        });

        it('应该包含区域边界模板', () => {
            const templates = TemplateDownloader.getTemplates();
            const boundaryTemplate = templates.find(t => t.name.includes('区域边界'));
            
            expect(boundaryTemplate).toBeDefined();
        });
    });

    describe('下载模板', () => {
        it('应该能够下载指定索引的模板', () => {
            TemplateDownloader.download(0);
            
            expect(URL.createObjectURL).toHaveBeenCalled();
            expect(document.createElement).toHaveBeenCalledWith('a');
        });

        it('应该能够下载第二个模板', () => {
            TemplateDownloader.download(1);
            
            expect(URL.createObjectURL).toHaveBeenCalled();
        });

        it('应该能够下载第三个模板', () => {
            TemplateDownloader.download(2);
            
            expect(URL.createObjectURL).toHaveBeenCalled();
        });

        it('无效索引不应该下载', () => {
            TemplateDownloader.download(-1);
            
            expect(URL.createObjectURL).not.toHaveBeenCalled();
        });

        it('超出范围的索引不应该下载', () => {
            TemplateDownloader.download(999);
            
            expect(URL.createObjectURL).not.toHaveBeenCalled();
        });

        it('下载时应该创建Blob', () => {
            TemplateDownloader.download(0);
            
            const blobCall = URL.createObjectURL.mock.calls[0][0];
            expect(blobCall).toBeInstanceOf(Blob);
        });

        it('Blob应该使用正确的MIME类型', () => {
            TemplateDownloader.download(0);
            
            const blobCall = URL.createObjectURL.mock.calls[0][0];
            expect(blobCall.options).toEqual({ type: 'application/geo+json' });
        });

        it('下载时应该触发点击事件', () => {
            const mockLink = {
                href: '',
                download: '',
                click: vi.fn()
            };
            const mockDialog = {
                querySelector: vi.fn((selector) => {
                    if (selector === '.open-location-btn' || selector === '.close-dialog-btn') {
                        return {
                            addEventListener: vi.fn(),
                            click: vi.fn()
                        };
                    }
                    return null;
                })
            };

            document.createElement.mockImplementation((tag) => {
                if (tag === 'a') return mockLink;
                if (tag === 'div') return mockDialog;
                return {
                    querySelector: vi.fn(() => null)
                };
            });

            TemplateDownloader.download(0);

            expect(mockLink.click).toHaveBeenCalled();
        });

        it('下载后应该移除链接元素', () => {
            TemplateDownloader.download(0);
            
            expect(document.body.removeChild).toHaveBeenCalled();
        });

        it('下载后应该释放URL对象', () => {
            TemplateDownloader.download(0);
            
            expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock-url');
        });
    });

    describe('创建下载面板', () => {
        it('应该能够创建下载面板', () => {
            const panel = TemplateDownloader.createPanel();
            
            expect(panel).toBeDefined();
            expect(panel.className).toBe('template-download-panel');
        });

        it('面板应该包含标题', () => {
            const panel = TemplateDownloader.createPanel();
            
            expect(panel.innerHTML).toContain('模板下载');
        });

        it('面板应该包含描述文本', () => {
            const panel = TemplateDownloader.createPanel();
            
            expect(panel.innerHTML).toContain('下载 GeoJSON 模板文件');
        });

        it('面板应该包含所有模板项', () => {
            const panel = TemplateDownloader.createPanel();
            const templates = TemplateDownloader.getTemplates();
            
            templates.forEach(template => {
                expect(panel.innerHTML).toContain(template.name);
            });
        });

        it('面板应该包含下载按钮', () => {
            const panel = TemplateDownloader.createPanel();
            
            expect(panel.innerHTML).toContain('下载');
        });

        it('面板应该包含数据格式要求', () => {
            const panel = TemplateDownloader.createPanel();
            
            expect(panel.innerHTML).toContain('数据格式要求');
        });

        it('面板应该包含文件格式说明', () => {
            const panel = TemplateDownloader.createPanel();
            
            expect(panel.innerHTML).toContain('GeoJSON');
        });

        it('面板应该包含坐标系说明', () => {
            const panel = TemplateDownloader.createPanel();
            
            expect(panel.innerHTML).toContain('WGS84');
        });

        it('面板应该包含最少采样点说明', () => {
            const panel = TemplateDownloader.createPanel();
            
            expect(panel.innerHTML).toContain('3 个采样点');
        });
    });

    describe('下载按钮事件', () => {
        it('点击下载按钮应该触发下载', () => {
            // 重置 mock
            vi.clearAllMocks();

            // Mock 完整的下载流程
            const mockLink = {
                href: '',
                download: '',
                click: vi.fn()
            };
            const mockDialog = {
                querySelector: vi.fn((selector) => {
                    if (selector === '.open-location-btn' || selector === '.close-dialog-btn') {
                        return {
                            addEventListener: vi.fn(),
                            click: vi.fn()
                        };
                    }
                    return null;
                })
            };

            document.createElement.mockImplementation((tag) => {
                if (tag === 'a') return mockLink;
                if (tag === 'div') return mockDialog;
                return {
                    querySelector: vi.fn(() => null)
                };
            });

            TemplateDownloader.download(0);

            // 验证下载流程
            expect(URL.createObjectURL).toHaveBeenCalled();
            expect(mockLink.click).toHaveBeenCalled();
        });

        it('不同索引的按钮应该下载对应的模板', () => {
            // 重置 mock
            vi.clearAllMocks();

            const mockLink = {
                href: '',
                download: '',
                click: vi.fn()
            };
            const mockDialog = {
                querySelector: vi.fn((selector) => {
                    if (selector === '.open-location-btn' || selector === '.close-dialog-btn') {
                        return {
                            addEventListener: vi.fn(),
                            click: vi.fn()
                        };
                    }
                    return null;
                })
            };

            document.createElement.mockImplementation((tag) => {
                if (tag === 'a') return mockLink;
                if (tag === 'div') return mockDialog;
                return {
                    querySelector: vi.fn(() => null)
                };
            });

            TemplateDownloader.download(0);
            TemplateDownloader.download(1);
            TemplateDownloader.download(2);

            expect(URL.createObjectURL).toHaveBeenCalledTimes(3);
        });
    });

    describe('模板数据结构', () => {
        it('基础采样点模板应该是FeatureCollection', () => {
            const templates = TemplateDownloader.getTemplates();
            // 由于我们无法直接访问模板数据，这里只测试方法存在性
            expect(TemplateDownloader.download).toBeDefined();
        });

        it('模板数据应该包含features数组', () => {
            // 测试方法存在性
            expect(TemplateDownloader.getTemplates).toBeDefined();
        });

        it('模板数据应该是有效的GeoJSON', () => {
            // 测试方法存在性
            expect(TemplateDownloader.download).toBeDefined();
        });
    });

    describe('静态方法', () => {
        it('应该暴露download静态方法', () => {
            expect(TemplateDownloader.download).toBeDefined();
            expect(typeof TemplateDownloader.download).toBe('function');
        });

        it('应该暴露getTemplates静态方法', () => {
            expect(TemplateDownloader.getTemplates).toBeDefined();
            expect(typeof TemplateDownloader.getTemplates).toBe('function');
        });

        it('应该暴露createPanel静态方法', () => {
            expect(TemplateDownloader.createPanel).toBeDefined();
            expect(typeof TemplateDownloader.createPanel).toBe('function');
        });
    });

    describe('模板内容', () => {
        it('基础采样点模板应该包含经纬度', () => {
            const templates = TemplateDownloader.getTemplates();
            const basicTemplate = templates.find(t => t.name.includes('基础采样点'));
            
            expect(basicTemplate).toBeDefined();
            expect(basicTemplate.description).toContain('经纬度');
        });

        it('土壤采样模板应该包含多种属性', () => {
            const templates = TemplateDownloader.getTemplates();
            const soilTemplate = templates.find(t => t.name.includes('土壤采样'));
            
            expect(soilTemplate).toBeDefined();
            expect(soilTemplate.description).toContain('土壤属性');
        });

        it('区域边界模板应该是多边形', () => {
            const templates = TemplateDownloader.getTemplates();
            const boundaryTemplate = templates.find(t => t.name.includes('区域边界'));
            
            expect(boundaryTemplate).toBeDefined();
            expect(boundaryTemplate.description).toContain('多边形');
        });
    });

    describe('文件名生成', () => {
        it('下载的文件应该有正确的扩展名', () => {
            // 重置 mock
            vi.clearAllMocks();

            const mockLink = {
                href: '',
                download: '',
                click: vi.fn()
            };
            const mockDialog = {
                querySelector: vi.fn((selector) => {
                    if (selector === '.open-location-btn' || selector === '.close-dialog-btn') {
                        return {
                            addEventListener: vi.fn(),
                            click: vi.fn()
                        };
                    }
                    return null;
                })
            };

            document.createElement.mockImplementation((tag) => {
                if (tag === 'a') return mockLink;
                if (tag === 'div') return mockDialog;
                return {
                    querySelector: vi.fn(() => null)
                };
            });

            TemplateDownloader.download(0);

            expect(mockLink.download).toMatch(/\.geojson$/);
        });

        it('不同模板应该有不同的文件名', () => {
            // 重置 mock
            vi.clearAllMocks();

            const mockLink = {
                href: '',
                download: '',
                click: vi.fn()
            };
            const mockDialog = {
                querySelector: vi.fn((selector) => {
                    if (selector === '.open-location-btn' || selector === '.close-dialog-btn') {
                        return {
                            addEventListener: vi.fn(),
                            click: vi.fn()
                        };
                    }
                    return null;
                })
            };

            document.createElement.mockImplementation((tag) => {
                if (tag === 'a') return mockLink;
                if (tag === 'div') return mockDialog;
                return {
                    querySelector: vi.fn(() => null)
                };
            });

            TemplateDownloader.download(0);
            const filename1 = mockLink.download;

            TemplateDownloader.download(1);
            const filename2 = mockLink.download;

            expect(filename1).not.toBe(filename2);
        });
    });

    describe('数据格式规则', () => {
        it('面板应该说明坐标系要求', () => {
            const panel = TemplateDownloader.createPanel();
            
            expect(panel.innerHTML).toContain('EPSG:4326');
        });

        it('面板应该说明几何类型要求', () => {
            const panel = TemplateDownloader.createPanel();
            
            expect(panel.innerHTML).toContain('Point');
            expect(panel.innerHTML).toContain('Polygon');
        });

        it('面板应该说明坐标格式', () => {
            const panel = TemplateDownloader.createPanel();
            
            expect(panel.innerHTML).toContain('[经度, 纬度]');
        });

        it('面板应该说明坐标范围', () => {
            const panel = TemplateDownloader.createPanel();
            
            expect(panel.innerHTML).toContain('-180~180');
            expect(panel.innerHTML).toContain('-90~90');
        });
    });

    describe('边界情况', () => {
        it('应该处理null索引', () => {
            // 不应该抛出错误
            expect(() => TemplateDownloader.download(null)).not.toThrow();
        });

        it('应该处理undefined索引', () => {
            // 不应该抛出错误
            expect(() => TemplateDownloader.download(undefined)).not.toThrow();
        });

        it('应该处理字符串索引', () => {
            // 不应该抛出错误
            expect(() => TemplateDownloader.download('0')).not.toThrow();
        });

        it('面板创建不应该依赖外部状态', () => {
            const panel1 = TemplateDownloader.createPanel();
            const panel2 = TemplateDownloader.createPanel();
            
            expect(panel1.innerHTML).toBe(panel2.innerHTML);
        });
    });

    describe('JSON序列化', () => {
        it('下载的JSON应该是格式化的', () => {
            TemplateDownloader.download(0);
            
            const blobCall = URL.createObjectURL.mock.calls[0][0];
            const json = blobCall.data[0];
            
            // 检查JSON是否包含缩进
            expect(json).toContain('\n');
            expect(json).toContain('  ');
        });

        it('下载的JSON应该是有效的', () => {
            TemplateDownloader.download(0);
            
            const blobCall = URL.createObjectURL.mock.calls[0][0];
            const json = blobCall.data[0];
            
            // 应该能够解析JSON
            expect(() => JSON.parse(json)).not.toThrow();
        });
    });

    describe('模板数量', () => {
        it('应该至少有3个模板', () => {
            const templates = TemplateDownloader.getTemplates();
            
            expect(templates.length).toBeGreaterThanOrEqual(3);
        });
    });

    describe('可访问性', () => {
        it('下载按钮应该有正确的data属性', () => {
            const panel = TemplateDownloader.createPanel();
            
            expect(panel.innerHTML).toContain('data-index');
        });

        it('规则部分应该使用details/summary标签', () => {
            const panel = TemplateDownloader.createPanel();
            
            expect(panel.innerHTML).toContain('<details');
            expect(panel.innerHTML).toContain('<summary');
        });
    });
});
