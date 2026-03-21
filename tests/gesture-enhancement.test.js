/**
 * 手势增强功能测试
 * 测试所有新增的手势功能
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

// Mock Capacitor Haptics
vi.mock('@capacitor/haptics', () => ({
    Haptics: {
        impact: vi.fn(),
        notification: vi.fn(),
    },
    ImpactStyle: {
        Light: 'light',
        Medium: 'medium',
        Heavy: 'heavy',
    },
}));

describe('TouchGestureManager Enhanced Features', () => {
    let container;
    let TouchGestureManager;

    beforeEach(async () => {
        // 创建测试容器
        container = document.createElement('div');
        container.style.width = '400px';
        container.style.height = '400px';
        document.body.appendChild(container);

        // 动态导入TouchGestureManager
        const module = await import('../apps/frontend/js/components/TouchGestureManager');
        TouchGestureManager = module.default;
    });

    afterEach(() => {
        if (container && container.parentNode) {
            container.parentNode.removeChild(container);
        }
    });

    describe('Triple Finger Pinch Gesture', () => {
        it('应该正确识别三指捏合手势', async () => {
            const manager = new TouchGestureManager({
                enableTripleFingerPinch: true,
            });

            const gestureEvents = [];
            manager.on('tripleFingerPinch', (event) => {
                gestureEvents.push(event);
            });

            manager.bind(container);

            // 模拟三指触摸开始
            const touchStartEvent = new TouchEvent('touchstart', {
                touches: [
                    { clientX: 100, clientY: 100, identifier: 1 },
                    { clientX: 150, clientY: 100, identifier: 2 },
                    { clientX: 125, clientY: 150, identifier: 3 },
                ],
            });
            container.dispatchEvent(touchStartEvent);

            // 模拟三指触摸移动
            const touchMoveEvent = new TouchEvent('touchmove', {
                touches: [
                    { clientX: 90, clientY: 90, identifier: 1 },
                    { clientX: 160, clientY: 90, identifier: 2 },
                    { clientX: 125, clientY: 160, identifier: 3 },
                ],
            });
            container.dispatchEvent(touchMoveEvent);

            // 验证三指手势被识别
            expect(gestureEvents.length).toBeGreaterThan(0);
            expect(gestureEvents[0].type).toBe('tripleFingerPinch');
            expect(gestureEvents[0].scale).toBeDefined();

            manager.destroy();
        });

        it('应该在禁用时忽略三指捏合手势', async () => {
            const manager = new TouchGestureManager({
                enableTripleFingerPinch: false,
            });

            const gestureEvents = [];
            manager.on('tripleFingerPinch', (event) => {
                gestureEvents.push(event);
            });

            manager.bind(container);

            // 模拟三指触摸
            const touchStartEvent = new TouchEvent('touchstart', {
                touches: [
                    { clientX: 100, clientY: 100, identifier: 1 },
                    { clientX: 150, clientY: 100, identifier: 2 },
                    { clientX: 125, clientY: 150, identifier: 3 },
                ],
            });
            container.dispatchEvent(touchStartEvent);

            // 验证三指手势被忽略
            expect(gestureEvents.length).toBe(0);

            manager.destroy();
        });
    });

    describe('Predictive Gesture Recognition', () => {
        it('应该在touchmove阶段高置信度提前触发滑动手势', async () => {
            const manager = new TouchGestureManager({
                enablePredictiveGesture: true,
                predictiveConfidenceThreshold: 0.9,
                predictiveMinMoveDistance: 20,
                enableQuickSwipe: false,
                enableLayerSwipe: false,
            });

            const swipeEvents = [];
            manager.on('swipe', (event) => {
                swipeEvents.push(event);
            });

            manager.bind(container);

            const touchStartEvent = new TouchEvent('touchstart', {
                touches: [{ clientX: 40, clientY: 200, identifier: 1 }],
            });
            container.dispatchEvent(touchStartEvent);

            const touchMoveEvent = new TouchEvent('touchmove', {
                touches: [{ clientX: 180, clientY: 210, identifier: 1 }],
                changedTouches: [{ clientX: 180, clientY: 210, identifier: 1 }],
            });
            container.dispatchEvent(touchMoveEvent);

            expect(swipeEvents.length).toBe(1);
            expect(swipeEvents[0].direction).toBe('right');

            const touchEndEvent = new TouchEvent('touchend', {
                changedTouches: [{ clientX: 190, clientY: 210, identifier: 1 }],
            });
            container.dispatchEvent(touchEndEvent);

            // 预测触发后不应在touchend重复触发同一滑动
            expect(swipeEvents.length).toBe(1);

            const metrics = manager.getPredictionMetrics();
            expect(metrics.totalPredictions).toBeGreaterThan(0);
            expect(metrics.highConfidencePredictions).toBeGreaterThan(0);

            manager.destroy();
        });
    });

    describe('Quick Swipe Gesture', () => {
        it('应该正确识别快速滑动手势', async () => {
            const manager = new TouchGestureManager({
                enableQuickSwipe: true,
                quickSwipeThreshold: 100,
            });

            const gestureEvents = [];
            manager.on('quickSwipe', (event) => {
                gestureEvents.push(event);
            });

            manager.bind(container);

            // 模拟快速滑动
            const touchStartEvent = new TouchEvent('touchstart', {
                touches: [{ clientX: 50, clientY: 200, identifier: 1 }],
            });
            container.dispatchEvent(touchStartEvent);

            const touchEndEvent = new TouchEvent('touchend', {
                changedTouches: [{ clientX: 200, clientY: 200, identifier: 1 }],
            });
            container.dispatchEvent(touchEndEvent);

            // 验证快速滑动被识别
            expect(gestureEvents.length).toBeGreaterThan(0);
            expect(gestureEvents[0].type).toBe('quickSwipe');
            expect(gestureEvents[0].velocity).toBeDefined();
            expect(gestureEvents[0].velocity).toBeGreaterThan(0.5);

            manager.destroy();
        });
    });

    describe('Layer Swipe Gesture', () => {
        it('应该正确识别图层切换手势', async () => {
            const manager = new TouchGestureManager({
                enableLayerSwipe: true,
            });

            const gestureEvents = [];
            manager.on('layerSwipe', (event) => {
                gestureEvents.push(event);
            });

            manager.bind(container);

            // 模拟长距离水平滑动
            const touchStartEvent = new TouchEvent('touchstart', {
                touches: [{ clientX: 50, clientY: 200, identifier: 1 }],
            });
            container.dispatchEvent(touchStartEvent);

            const touchEndEvent = new TouchEvent('touchend', {
                changedTouches: [{ clientX: 200, clientY: 200, identifier: 1 }],
            });
            container.dispatchEvent(touchEndEvent);

            // 验证图层切换手势被识别
            expect(gestureEvents.length).toBeGreaterThan(0);
            expect(gestureEvents[0].type).toBe('layerSwipe');
            expect(gestureEvents[0].layerIndex).toBeDefined();

            manager.destroy();
        });
    });

    describe('Gesture Conflict Detection', () => {
        it('应该正确处理手势冲突', async () => {
            const manager = new TouchGestureManager({
                enableGestureConflictDetection: true,
            });

            const tapEvents = [];
            const longPressEvents = [];

            manager.on('tap', (event) => {
                tapEvents.push(event);
            });

            manager.on('longPress', (event) => {
                longPressEvents.push(event);
            });

            manager.bind(container);

            // 模拟长按
            const touchStartEvent = new TouchEvent('touchstart', {
                touches: [{ clientX: 200, clientY: 200, identifier: 1 }],
            });
            container.dispatchEvent(touchStartEvent);

            // 等待长按延迟
            await new Promise((resolve) => setTimeout(resolve, 600));

            // 验证长按优先级高于点击
            expect(longPressEvents.length).toBeGreaterThan(0);
            expect(tapEvents.length).toBe(0);

            manager.destroy();
        });

        it('应该允许高优先级手势覆盖低优先级手势', async () => {
            const manager = new TouchGestureManager({
                enableGestureConflictDetection: true,
            });

            manager.bind(container);

            // 设置手势优先级
            manager.setGesturePriority('longPress', 10);
            manager.setGesturePriority('tap', 4);

            expect(manager.getGesturePriority('longPress')).toBe(10);
            expect(manager.getGesturePriority('tap')).toBe(4);

            manager.destroy();
        });
    });

    describe('Undo/Redo Functionality', () => {
        it('应该正确保存手势历史', async () => {
            const manager = new TouchGestureManager({
                enableUndoRedo: true,
                maxUndoSteps: 10,
            });

            manager.bind(container);

            // 模拟多次点击
            for (let i = 0; i < 3; i++) {
                const touchStartEvent = new TouchEvent('touchstart', {
                    touches: [{ clientX: 200, clientY: 200, identifier: i }],
                });
                container.dispatchEvent(touchStartEvent);

                const touchEndEvent = new TouchEvent('touchend', {
                    changedTouches: [{ clientX: 200, clientY: 200, identifier: i }],
                });
                container.dispatchEvent(touchEndEvent);
            }

            // 验证历史记录
            const history = manager.getHistory();
            expect(history.length).toBe(3);

            manager.destroy();
        });

        it('应该支持撤销操作', async () => {
            const manager = new TouchGestureManager({
                enableUndoRedo: true,
            });

            manager.bind(container);

            // 模拟一次点击
            const touchStartEvent = new TouchEvent('touchstart', {
                touches: [{ clientX: 200, clientY: 200, identifier: 1 }],
            });
            container.dispatchEvent(touchStartEvent);

            const touchEndEvent = new TouchEvent('touchend', {
                changedTouches: [{ clientX: 200, clientY: 200, identifier: 1 }],
            });
            container.dispatchEvent(touchEndEvent);

            // 撤销
            const undoneGesture = manager.undo();
            expect(undoneGesture).toBeDefined();
            expect(undoneGesture?.type).toBe('tap');

            // 验证历史记录减少
            const history = manager.getHistory();
            expect(history.length).toBe(0);

            manager.destroy();
        });

        it('应该支持重做操作', async () => {
            const manager = new TouchGestureManager({
                enableUndoRedo: true,
            });

            manager.bind(container);

            // 模拟一次点击
            const touchStartEvent = new TouchEvent('touchstart', {
                touches: [{ clientX: 200, clientY: 200, identifier: 1 }],
            });
            container.dispatchEvent(touchStartEvent);

            const touchEndEvent = new TouchEvent('touchend', {
                changedTouches: [{ clientX: 200, clientY: 200, identifier: 1 }],
            });
            container.dispatchEvent(touchEndEvent);

            // 撤销
            manager.undo();

            // 重做
            const redoneGesture = manager.redo();
            expect(redoneGesture).toBeDefined();
            expect(redoneGesture?.type).toBe('tap');

            // 验证历史记录恢复
            const history = manager.getHistory();
            expect(history.length).toBe(1);

            manager.destroy();
        });

        it('应该限制历史记录长度', async () => {
            const manager = new TouchGestureManager({
                enableUndoRedo: true,
                maxUndoSteps: 5,
            });

            manager.bind(container);

            // 模拟10次点击
            for (let i = 0; i < 10; i++) {
                const touchStartEvent = new TouchEvent('touchstart', {
                    touches: [{ clientX: 200, clientY: 200, identifier: i }],
                });
                container.dispatchEvent(touchStartEvent);

                const touchEndEvent = new TouchEvent('touchend', {
                    changedTouches: [{ clientX: 200, clientY: 200, identifier: i }],
                });
                container.dispatchEvent(touchEndEvent);
            }

            // 验证历史记录不超过最大值
            const history = manager.getHistory();
            expect(history.length).toBeLessThanOrEqual(5);

            manager.destroy();
        });
    });

    describe('Haptic Feedback', () => {
        it('应该在点击时提供触觉反馈', async () => {
            const { Haptics, ImpactStyle } = await import('@capacitor/haptics');

            const manager = new TouchGestureManager({
                enableHaptic: true,
            });

            manager.bind(container);

            // 模拟点击
            const touchStartEvent = new TouchEvent('touchstart', {
                touches: [{ clientX: 200, clientY: 200, identifier: 1 }],
            });
            container.dispatchEvent(touchStartEvent);

            const touchEndEvent = new TouchEvent('touchend', {
                changedTouches: [{ clientX: 200, clientY: 200, identifier: 1 }],
            });
            container.dispatchEvent(touchEndEvent);

            // 验证触觉反馈被调用
            expect(Haptics.impact).toHaveBeenCalledWith({
                style: ImpactStyle.Light,
            });

            manager.destroy();
        });

        it('应该在手势成功时提供触觉反馈', async () => {
            const { Haptics, ImpactStyle } = await import('@capacitor/haptics');

            const manager = new TouchGestureManager({
                enableHaptic: true,
            });

            manager.bind(container);

            // 模拟长按
            const touchStartEvent = new TouchEvent('touchstart', {
                touches: [{ clientX: 200, clientY: 200, identifier: 1 }],
            });
            container.dispatchEvent(touchStartEvent);

            // 等待长按延迟
            await new Promise((resolve) => setTimeout(resolve, 600));

            // 验证触觉反馈被调用
            expect(Haptics.impact).toHaveBeenCalledWith({
                style: ImpactStyle.Heavy,
            });

            manager.destroy();
        });
    });

    describe('Visual Feedback', () => {
        it('应该在手势触发时显示视觉反馈', async () => {
            const manager = new TouchGestureManager({
                enableVisualFeedback: true,
            });

            manager.bind(container);

            // 模拟点击
            const touchStartEvent = new TouchEvent('touchstart', {
                touches: [{ clientX: 200, clientY: 200, identifier: 1 }],
            });
            container.dispatchEvent(touchStartEvent);

            const touchEndEvent = new TouchEvent('touchend', {
                changedTouches: [{ clientX: 200, clientY: 200, identifier: 1 }],
            });
            container.dispatchEvent(touchEndEvent);

            // 验证反馈元素存在
            const feedbackElement = container.querySelector('.feedback-element');
            expect(feedbackElement).toBeDefined();

            manager.destroy();
        });
    });

    describe('Gesture State Management', () => {
        it('应该正确跟踪活动手势', async () => {
            const manager = new TouchGestureManager();

            manager.bind(container);

            // 模拟双指触摸
            const touchStartEvent = new TouchEvent('touchstart', {
                touches: [
                    { clientX: 100, clientY: 100, identifier: 1 },
                    { clientX: 150, clientY: 100, identifier: 2 },
                ],
            });
            container.dispatchEvent(touchStartEvent);

            // 验证活动手势
            const activeGesture = manager.getActiveGesture();
            expect(activeGesture).toBe('pinch');

            manager.destroy();
        });
    });
});

describe('GestureTutorial', () => {
    let container;
    let GestureTutorial;

    beforeEach(async () => {
        container = document.createElement('div');
        container.style.width = '400px';
        container.style.height = '400px';
        document.body.appendChild(container);

        const module = await import('../apps/frontend/js/components/GestureTutorial');
        GestureTutorial = module.default;
    });

    afterEach(() => {
        if (container && container.parentNode) {
            container.parentNode.removeChild(container);
        }
    });

    it('应该正确初始化教程', async () => {
        const tutorial = new GestureTutorial({
            autoShow: false,
        });

        tutorial.init(container);

        expect(tutorial).toBeDefined();
    });

    it('应该显示教程步骤', async () => {
        const tutorial = new GestureTutorial({
            autoShow: false,
        });

        tutorial.init(container);
        tutorial.show();

        // 验证教程覆盖层存在
        const tutorialOverlay = container.querySelector('.gesture-tutorial-overlay');
        expect(tutorialOverlay).toBeDefined();

        tutorial.destroy();
    });

    it('应该支持步骤导航', async () => {
        const tutorial = new GestureTutorial({
            autoShow: false,
        });

        tutorial.init(container);
        tutorial.show();

        // 验证当前步骤
        let currentStep = tutorial.getCurrentStep();
        expect(currentStep).toBeDefined();
        expect(currentStep?.id).toBe('tap');

        // 导航到下一步
        tutorial.nextStep();
        currentStep = tutorial.getCurrentStep();
        expect(currentStep?.id).toBe('doubleTap');

        // 导航到上一步
        tutorial.previousStep();
        currentStep = tutorial.getCurrentStep();
        expect(currentStep?.id).toBe('tap');

        tutorial.destroy();
    });

    it('应该支持完成教程', async () => {
        const tutorial = new GestureTutorial({
            autoShow: false,
        });

        tutorial.init(container);
        tutorial.show();

        // 完成教程
        tutorial.completeTutorial();

        // 验证教程被隐藏
        const tutorialOverlay = container.querySelector('.gesture-tutorial-overlay');
        expect(tutorialOverlay).toBeNull();

        tutorial.destroy();
    });

    it('应该支持重置教程', async () => {
        const tutorial = new GestureTutorial({
            autoShow: false,
        });

        tutorial.init(container);
        tutorial.show();
        tutorial.completeTutorial();

        // 重置教程
        tutorial.resetTutorial();

        // 验证教程可以重新显示
        tutorial.show();
        const tutorialOverlay = container.querySelector('.gesture-tutorial-overlay');
        expect(tutorialOverlay).toBeDefined();

        tutorial.destroy();
    });
});

describe('GestureSettingsPanel', () => {
    let container;
    let GestureSettingsPanel;
    let TouchGestureManager;

    beforeEach(async () => {
        container = document.createElement('div');
        container.style.width = '400px';
        container.style.height = '400px';
        document.body.appendChild(container);

        const [settingsModule, gestureModule] = await Promise.all([
            import('../apps/frontend/js/components/GestureSettingsPanel'),
            import('../apps/frontend/js/components/TouchGestureManager'),
        ]);

        GestureSettingsPanel = settingsModule.default;
        TouchGestureManager = gestureModule.default;
    });

    afterEach(() => {
        if (container && container.parentNode) {
            container.parentNode.removeChild(container);
        }
    });

    it('应该正确初始化设置面板', async () => {
        const gestureManager = new TouchGestureManager();
        const panel = new GestureSettingsPanel({
            gestureManager,
        });

        panel.init(container);

        expect(panel).toBeDefined();
    });

    it('应该显示设置面板', async () => {
        const gestureManager = new TouchGestureManager();
        const panel = new GestureSettingsPanel({
            gestureManager,
        });

        panel.init(container);
        panel.show();

        // 验证面板存在
        const settingsPanel = container.querySelector('.gesture-settings-panel');
        expect(settingsPanel).toBeDefined();

        panel.destroy();
    });

    it('应该支持保存设置', async () => {
        const gestureManager = new TouchGestureManager();
        const panel = new GestureSettingsPanel({
            gestureManager,
        });

        panel.init(container);
        panel.show();

        // 保存设置
        panel.applySettings();

        // 验证设置被应用
        expect(gestureManager).toBeDefined();

        panel.destroy();
    });

    it('应该支持重置设置', async () => {
        const gestureManager = new TouchGestureManager();
        const panel = new GestureSettingsPanel({
            gestureManager,
        });

        panel.init(container);
        panel.show();

        // 重置设置
        panel.resetToDefaults();

        // 验证设置被重置
        expect(gestureManager).toBeDefined();

        panel.destroy();
    });
});
