/**
 * 自定义下拉组件
 * 支持深色模式的下拉选择器，替换原生 select 元素
 */

interface SelectOption {
    value: string;
    label: string;
}

interface CustomSelectOptions {
    name?: string;
    value?: string;
    options: SelectOption[];
    onChange?: (value: string) => void;
    className?: string;
}

export class CustomSelect {
    private container: HTMLElement;
    private select!: HTMLElement;
    private dropdown!: HTMLElement;
    private selectedText!: HTMLElement;
    private options: SelectOption[];
    private currentValue: string;
    private isOpen: boolean;
    private onChange: ((value: string) => void) | null;
    private name: string;
    private focusedIndex: number;

    constructor(container: HTMLElement | string, options: CustomSelectOptions) {
        this.container = typeof container === 'string'
            ? document.querySelector(container)!
            : container;
        
        this.name = options.name || '';
        this.options = options.options;
        this.currentValue = options.value || options.options[0]?.value || '';
        this.onChange = options.onChange || null;
        this.isOpen = false;
        this.focusedIndex = -1;
        
        this.init();
    }

    private init(): void {
        this.createSelect();
        this.bindEvents();
    }

    private createSelect(): void {
        // 创建容器
        const wrapper = document.createElement('div');
        wrapper.className = `custom-select-wrapper ${this.name ? `custom-select-${this.name}` : ''}`;

        // 创建选择器头部
        this.select = document.createElement('div');
        this.select.className = 'custom-select';
        this.select.setAttribute('role', 'combobox');
        this.select.setAttribute('aria-expanded', 'false');
        this.select.setAttribute('tabindex', '0');

        // 当前选中值的显示
        this.selectedText = document.createElement('div');
        this.selectedText.className = 'custom-select-value';
        this.selectedText.textContent = this.getLabel(this.currentValue);

        // 下拉箭头
        const arrow = document.createElement('div');
        arrow.className = 'custom-select-arrow';
        arrow.innerHTML = `
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="2 4 6 8 10 4"></polyline>
            </svg>
        `;

        this.select.appendChild(this.selectedText);
        this.select.appendChild(arrow);

        // 创建下拉列表
        this.dropdown = document.createElement('div');
        this.dropdown.className = 'custom-select-dropdown';
        this.dropdown.setAttribute('role', 'listbox');

        // 创建选项
        this.options.forEach((option, index) => {
            const optionElement = document.createElement('div');
            optionElement.className = 'custom-select-option';
            optionElement.setAttribute('role', 'option');
            optionElement.setAttribute('data-value', option.value);
            optionElement.setAttribute('data-index', index.toString());
            optionElement.textContent = option.label;
            
            if (option.value === this.currentValue) {
                optionElement.classList.add('custom-select-option-selected');
            }
            
            this.dropdown.appendChild(optionElement);
        });

        // 默认隐藏下拉列表
        this.dropdown.style.display = 'none';

        wrapper.appendChild(this.select);
        wrapper.appendChild(this.dropdown);
        this.container.appendChild(wrapper);
    }

    private bindEvents(): void {
        // 点击选择器头部
        this.select.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggle();
        });

        // 点击选项
        this.dropdown.addEventListener('click', (e) => {
            const target = e.target as HTMLElement;
            if (target.classList.contains('custom-select-option')) {
                const value = target.getAttribute('data-value')!;
                this.setValue(value);
                this.close();
            }
        });

        // 键盘导航
        this.select.addEventListener('keydown', (e) => {
            this.handleKeyDown(e);
        });

        // 点击外部关闭
        document.addEventListener('click', (e) => {
            if (!this.container.contains(e.target as Node)) {
                this.close();
            }
        });

        // 主题变化时更新样式
        this.observeThemeChange();
    }

    private handleKeyDown(e: KeyboardEvent): void {
        switch (e.key) {
            case 'Enter':
            case ' ':
                e.preventDefault();
                if (this.isOpen && this.focusedIndex >= 0) {
                    const option = this.options[this.focusedIndex];
                    if (option) {
                        this.setValue(option.value);
                        this.close();
                    }
                } else {
                    this.toggle();
                }
                break;
            case 'Escape':
                e.preventDefault();
                this.close();
                break;
            case 'ArrowDown':
                e.preventDefault();
                if (!this.isOpen) {
                    this.open();
                } else {
                    this.focusNextOption();
                }
                break;
            case 'ArrowUp':
                e.preventDefault();
                if (this.isOpen) {
                    this.focusPreviousOption();
                }
                break;
            case 'Home':
                e.preventDefault();
                if (this.isOpen) {
                    this.focusOption(0);
                }
                break;
            case 'End':
                e.preventDefault();
                if (this.isOpen) {
                    this.focusOption(this.options.length - 1);
                }
                break;
        }
    }

    private focusNextOption(): void {
        const newIndex = this.focusedIndex < this.options.length - 1 ? this.focusedIndex + 1 : 0;
        this.focusOption(newIndex);
    }

    private focusPreviousOption(): void {
        const newIndex = this.focusedIndex > 0 ? this.focusedIndex - 1 : this.options.length - 1;
        this.focusOption(newIndex);
    }

    private focusOption(index: number): void {
        this.focusedIndex = index;
        
        // 移除所有焦点样式
        const options = this.dropdown.querySelectorAll('.custom-select-option');
        options.forEach(opt => opt.classList.remove('custom-select-option-focused'));
        
        // 添加焦点样式到当前选项
        const currentOption = options[index];
        if (currentOption) {
            currentOption.classList.add('custom-select-option-focused');
            currentOption.scrollIntoView({ block: 'nearest' });
        }
    }

    private observeThemeChange(): void {
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === 'attributes' && mutation.attributeName === 'data-theme') {
                    // 主题变化时重新渲染
                    this.updateTheme();
                }
            });
        });

        observer.observe(document.documentElement, {
            attributes: true,
            attributeFilter: ['data-theme', 'class']
        });

        // 监听系统主题变化
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
            this.updateTheme();
        });
    }

    private updateTheme(): void {
        // 主题变化时的更新逻辑（如果有需要）
        // const _isDark = document.documentElement.getAttribute('data-theme') === 'dark' ||
        //                window.matchMedia('(prefers-color-scheme: dark)').matches;

        // 根据主题可以添加特定的样式或行为
    }

    private toggle(): void {
        if (this.isOpen) {
            this.close();
        } else {
            this.open();
        }
    }

    private open(): void {
        this.isOpen = true;
        this.dropdown.style.display = 'block';
        this.select.setAttribute('aria-expanded', 'true');
        this.select.classList.add('custom-select-open');
        
        // 设置初始焦点
        const currentIndex = this.options.findIndex(opt => opt.value === this.currentValue);
        this.focusOption(currentIndex >= 0 ? currentIndex : 0);
        
        // 确保下拉列表在视口中可见
        this.adjustDropdownPosition();
    }

    private close(): void {
        this.isOpen = false;
        this.dropdown.style.display = 'none';
        this.select.setAttribute('aria-expanded', 'false');
        this.select.classList.remove('custom-select-open');
        this.focusedIndex = -1;
        
        // 清除焦点样式
        const options = this.dropdown.querySelectorAll('.custom-select-option');
        options.forEach(opt => opt.classList.remove('custom-select-option-focused'));
    }

    private adjustDropdownPosition(): void {
        const selectRect = this.select.getBoundingClientRect();
        const dropdownRect = this.dropdown.getBoundingClientRect();
        const viewportHeight = window.innerHeight;
        
        // 检查下拉列表是否超出视口底部
        if (selectRect.bottom + dropdownRect.height > viewportHeight) {
            // 尝试向上显示
            if (selectRect.top >= dropdownRect.height) {
                this.dropdown.style.top = 'auto';
                this.dropdown.style.bottom = '100%';
                this.dropdown.style.marginTop = '0';
                this.dropdown.style.marginBottom = '4px';
            } else {
                // 如果上下都不够，使用滚动
                this.dropdown.style.maxHeight = `${viewportHeight - selectRect.bottom - 10}px`;
                this.dropdown.style.overflowY = 'auto';
            }
        } else {
            // 向下显示
            this.dropdown.style.top = '100%';
            this.dropdown.style.bottom = 'auto';
            this.dropdown.style.marginTop = '4px';
            this.dropdown.style.marginBottom = '0';
            this.dropdown.style.maxHeight = '';
            this.dropdown.style.overflowY = '';
        }
    }

    private getLabel(value: string): string {
        const option = this.options.find(opt => opt.value === value);
        return option ? option.label : '';
    }

    public setValue(value: string): void {
        if (this.currentValue === value) return;
        
        this.currentValue = value;
        this.selectedText.textContent = this.getLabel(value);
        
        // 更新选中状态
        const options = this.dropdown.querySelectorAll('.custom-select-option');
        options.forEach(opt => {
            const optValue = opt.getAttribute('data-value');
            if (optValue === value) {
                opt.classList.add('custom-select-option-selected');
            } else {
                opt.classList.remove('custom-select-option-selected');
            }
        });
        
        // 触发变更事件
        if (this.onChange) {
            this.onChange(value);
        }
    }

    public getValue(): string {
        return this.currentValue;
    }

    public setOptions(options: SelectOption[]): void {
        this.options = options;
        
        // 重建选项列表
        this.dropdown.innerHTML = '';
        this.options.forEach((option, index) => {
            const optionElement = document.createElement('div');
            optionElement.className = 'custom-select-option';
            optionElement.setAttribute('role', 'option');
            optionElement.setAttribute('data-value', option.value);
            optionElement.setAttribute('data-index', index.toString());
            optionElement.textContent = option.label;
            
            if (option.value === this.currentValue) {
                optionElement.classList.add('custom-select-option-selected');
            }
            
            this.dropdown.appendChild(optionElement);
        });
        
        // 如果当前值不在新选项中，选择第一个选项
        if (!this.options.find(opt => opt.value === this.currentValue)) {
            this.setValue(this.options[0]?.value || '');
        }
    }

    public enable(): void {
        this.select.setAttribute('tabindex', '0');
        this.select.classList.remove('custom-select-disabled');
    }

    public disable(): void {
        this.select.setAttribute('tabindex', '-1');
        this.select.classList.add('custom-select-disabled');
    }

    public destroy(): void {
        const wrapper = this.container.querySelector('.custom-select-wrapper');
        if (wrapper) {
            wrapper.remove();
        }
    }
}