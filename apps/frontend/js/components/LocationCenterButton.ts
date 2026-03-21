/**
 * 回到中心按钮组件
 * 在高德地图中显示"回到中心"按钮，点击后返回定位蓝点位置
 */

/**
 * 回到中心按钮组件
 */
export class LocationCenterButton {
    /** 按钮元素 */
    private button: HTMLElement | null = null;

    /** 回到中心回调函数 */
    private onCenter: (() => void) | null = null;

    /** 是否可见 */
    private isVisible: boolean = false;

    /** 是否正在执行 */
    private isAnimating: boolean = false;

    constructor(onCenter?: () => void) {
        this.onCenter = onCenter || null;
    }

    /**
     * 创建按钮
     */
    createButton(): HTMLElement {
        this.button = document.createElement('div');
        this.button.className = 'location-center-button';
        this.button.title = '回到当前位置';
        this.button.style.display = 'none'; // 默认隐藏

        // 样式
        this.button.style.cssText = `
            position: absolute;
            bottom: 24px;
            right: 24px;
            width: 48px;
            height: 48px;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.95);
            box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            font-size: 20px;
            z-index: 9999;
            transition: all 0.3s ease;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(0, 0, 0, 0.08);
            user-select: none;
            -webkit-user-select: none;
        `;

        // 图标
        const icon = document.createElement('span');
        icon.innerHTML = '📍';
        icon.style.fontSize = '20px';
        icon.style.lineHeight = '1';

        // 添加到按钮
        this.button.appendChild(icon);

        // Hover 效果
        this.button.addEventListener('mouseenter', () => {
            if (!this.isAnimating && this.button) {
                this.button.style.background = 'rgba(255, 255, 255, 1)';
                this.button.style.transform = 'scale(1.1)';
                this.button.style.boxShadow = '0 4px 16px rgba(0, 0, 0, 0.2)';
            }
        });

        this.button.addEventListener('mouseleave', () => {
            if (!this.isAnimating && this.button) {
                this.button.style.background = 'rgba(255, 255, 255, 0.95)';
                this.button.style.transform = 'scale(1)';
                this.button.style.boxShadow = '0 2px 12px rgba(0, 0, 0, 0.15)';
            }
        });

        // 点击事件
        this.button.addEventListener('click', () => this.handleClick());

        return this.button;
    }

    /**
     * 处理点击事件
     */
    private handleClick(): void {
        if (this.isAnimating || !this.onCenter) {
            return;
        }

        // 添加涟漪效果
        this.addRippleEffect();

        // 执行回到中心
        if (this.onCenter) {
            this.onCenter();
        }
    }

    /**
     * 添加涟漪效果
     */
    private addRippleEffect(): void {
        if (!this.button) return;

        const ripple = document.createElement('span');
        ripple.style.cssText = `
            position: absolute;
            width: 48px;
            height: 48px;
            border-radius: 50%;
            background: rgba(74, 144, 226, 0.3);
            animation: ripple 0.6s ease-out;
            pointer-events: none;
        `;

        // 添加动画样式
        const style = document.createElement('style');
        style.textContent = `
            @keyframes ripple {
                0% {
                    transform: scale(0);
                    opacity: 1;
                }
                100% {
                    transform: scale(2);
                    opacity: 0;
                }
            }
        `;
        if (!document.head.querySelector(`style[data-ripple]`)) {
            style.setAttribute('data-ripple', 'true');
            document.head.appendChild(style);
        }

        this.button.appendChild(ripple);

        ripple.addEventListener('animationend', () => {
            ripple.remove();
        });
    }

    /**
     * 添加到容器
     */
    addToContainer(container: HTMLElement): void {
        if (!this.button) {
            this.button = this.createButton();
        }
        container.appendChild(this.button);
    }

    /**
     * 显示按钮
     */
    show(): void {
        if (this.button) {
            this.button.style.display = 'flex';
            this.isVisible = true;
            console.log('✅ 回到中心按钮已显示');
        }
    }

    /**
     * 隐藏按钮
     */
    hide(): void {
        if (this.button) {
            this.button.style.display = 'none';
            this.isVisible = false;
            console.log('✅ 回到中心按钮已隐藏');
        }
    }

    /**
     * 设置回到中心回调
     */
    setOnCenter(callback: () => void): void {
        this.onCenter = callback;
    }

    /**
     * 销毁按钮
     */
    destroy(): void {
        if (this.button && this.button.parentNode) {
            this.button.parentNode.removeChild(this.button);
        }
        this.button = null;
        this.onCenter = null;
        this.isVisible = false;
    }

    /**
     * 获取按钮元素
     */
    getElement(): HTMLElement | null {
        return this.button;
    }

    /**
     * 检查按钮是否可见
     */
    getIsVisible(): boolean {
        return this.isVisible;
    }
}