import { APIService } from '../../services/API封装.js';

export type PanelFieldType = 'text' | 'number' | 'textarea' | 'json' | 'checkbox' | 'select';

export interface PanelFieldOption {
    label: string;
    value: string;
}

export interface PanelField {
    key: string;
    label: string;
    type: PanelFieldType;
    required?: boolean;
    placeholder?: string;
    defaultValue?: unknown;
    options?: PanelFieldOption[];
    rows?: number;
}

export interface PanelOperation {
    id: string;
    label: string;
    method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
    path: string;
    bodyFromFields?: string[];
    bodyFieldAsRoot?: string;
}

export interface PanelConfig {
    key: string;
    title: string;
    description: string;
    fields: PanelField[];
    operations: PanelOperation[];
}

export class ConfigurableApiPanel {
    protected root: HTMLElement | null = null;
    private fieldElements: Map<string, HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement> = new Map();
    private resultElement: HTMLElement | null = null;
    private statusElement: HTMLElement | null = null;

    constructor(
        protected readonly apiService: APIService,
        protected readonly config: PanelConfig
    ) {}

    public mount(container: HTMLElement): void {
        this.root = document.createElement('div');
        this.root.className = 'integration-module-panel';
        this.root.setAttribute('data-panel-key', this.config.key);

        const title = document.createElement('h3');
        title.className = 'integration-module-title';
        title.textContent = this.config.title;

        const description = document.createElement('p');
        description.className = 'integration-module-description';
        description.textContent = this.config.description;

        const form = document.createElement('div');
        form.className = 'integration-form-grid';

        this.config.fields.forEach((field) => {
            const fieldWrapper = document.createElement('div');
            fieldWrapper.className = 'integration-field';

            const label = document.createElement('label');
            label.className = 'integration-field-label';
            label.textContent = field.label;
            label.setAttribute('for', `${this.config.key}-${field.key}`);

            const input = this.createFieldElement(field);
            input.id = `${this.config.key}-${field.key}`;
            this.fieldElements.set(field.key, input);

            fieldWrapper.appendChild(label);
            fieldWrapper.appendChild(input);
            form.appendChild(fieldWrapper);
        });

        const actions = document.createElement('div');
        actions.className = 'integration-actions';

        this.config.operations.forEach((operation) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'btn btn-secondary integration-action-btn';
            button.setAttribute('data-operation-id', operation.id);
            button.textContent = operation.label;
            button.addEventListener('click', async () => {
                await this.executeOperation(operation);
            });
            actions.appendChild(button);
        });

        this.statusElement = document.createElement('div');
        this.statusElement.className = 'status-message';

        this.resultElement = document.createElement('pre');
        this.resultElement.className = 'integration-result';
        this.resultElement.textContent = '等待操作...';

        this.root.appendChild(title);
        this.root.appendChild(description);
        this.root.appendChild(form);
        this.root.appendChild(actions);
        this.root.appendChild(this.statusElement);
        this.root.appendChild(this.resultElement);

        container.appendChild(this.root);
    }

    private createFieldElement(field: PanelField): HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement {
        if (field.type === 'textarea' || field.type === 'json') {
            const textarea = document.createElement('textarea');
            textarea.className = 'input integration-input integration-textarea';
            textarea.rows = field.rows || (field.type === 'json' ? 8 : 4);
            if (field.placeholder) {
                textarea.placeholder = field.placeholder;
            }
            if (typeof field.defaultValue !== 'undefined') {
                if (field.type === 'json' && typeof field.defaultValue !== 'string') {
                    textarea.value = JSON.stringify(field.defaultValue, null, 2);
                } else {
                    textarea.value = String(field.defaultValue);
                }
            }
            return textarea;
        }

        if (field.type === 'select') {
            const select = document.createElement('select');
            select.className = 'select integration-input';
            (field.options || []).forEach((option) => {
                const optionElement = document.createElement('option');
                optionElement.value = option.value;
                optionElement.textContent = option.label;
                select.appendChild(optionElement);
            });
            if (typeof field.defaultValue !== 'undefined') {
                select.value = String(field.defaultValue);
            }
            return select;
        }

        const input = document.createElement('input');
        input.className = 'input integration-input';
        input.type = field.type === 'checkbox' ? 'checkbox' : field.type;

        if (field.type === 'checkbox') {
            input.classList.add('integration-checkbox');
            input.checked = Boolean(field.defaultValue);
        } else {
            if (field.placeholder) {
                input.placeholder = field.placeholder;
            }
            if (typeof field.defaultValue !== 'undefined') {
                input.value = String(field.defaultValue);
            }
        }

        return input;
    }

    private getFieldValue(field: PanelField): unknown {
        const element = this.fieldElements.get(field.key);
        if (!element) {
            return undefined;
        }

        if (field.type === 'checkbox') {
            return (element as HTMLInputElement).checked;
        }

        const rawValue = element.value.trim();

        if (!rawValue) {
            return '';
        }

        if (field.type === 'number') {
            const numberValue = Number(rawValue);
            return Number.isNaN(numberValue) ? rawValue : numberValue;
        }

        if (field.type === 'json') {
            try {
                return JSON.parse(rawValue);
            } catch {
                throw new Error(`${field.label} 不是有效 JSON`);
            }
        }

        return rawValue;
    }

    private collectFieldValues(): Record<string, unknown> {
        const values: Record<string, unknown> = {};

        this.config.fields.forEach((field) => {
            const value = this.getFieldValue(field);
            if (field.required && (value === '' || typeof value === 'undefined')) {
                throw new Error(`${field.label} 为必填项`);
            }
            values[field.key] = value;
        });

        return values;
    }

    private buildPath(template: string, values: Record<string, unknown>): string {
        return template.replace(/:([A-Za-z0-9_]+)/g, (_, key: string) => {
            const value = values[key];
            if (value === '' || value === null || typeof value === 'undefined') {
                throw new Error(`缺少路径参数: ${key}`);
            }
            return encodeURIComponent(String(value));
        });
    }

    private buildBody(operation: PanelOperation, values: Record<string, unknown>): unknown {
        if (operation.bodyFieldAsRoot) {
            return values[operation.bodyFieldAsRoot];
        }

        if (operation.bodyFromFields && operation.bodyFromFields.length > 0) {
            const body: Record<string, unknown> = {};
            operation.bodyFromFields.forEach((fieldKey) => {
                body[fieldKey] = values[fieldKey];
            });
            return body;
        }

        return undefined;
    }

    private setStatus(message: string, type: 'success' | 'error' | 'warning' = 'success'): void {
        if (!this.statusElement) {
            return;
        }
        this.statusElement.className = `status-message ${type}`;
        this.statusElement.textContent = message;
    }

    private setResult(data: unknown): void {
        if (!this.resultElement) {
            return;
        }
        this.resultElement.textContent = JSON.stringify(data, null, 2);
    }

    private setLoading(loading: boolean): void {
        if (!this.root) {
            return;
        }
        this.root.querySelectorAll('button.integration-action-btn').forEach((button) => {
            (button as HTMLButtonElement).disabled = loading;
        });
    }

    private async executeOperation(operation: PanelOperation): Promise<void> {
        try {
            this.setLoading(true);
            this.setStatus(`正在执行: ${operation.label}`, 'warning');

            const values = this.collectFieldValues();
            const path = this.buildPath(operation.path, values);
            const url = `${this.apiService.baseURL}${path}`;

            const options: RequestInit = {
                method: operation.method
            };

            if (operation.method !== 'GET') {
                const body = this.buildBody(operation, values);
                if (typeof body !== 'undefined') {
                    options.headers = { 'Content-Type': 'application/json' };
                    options.body = JSON.stringify(body);
                }
            }

            const response = await this.apiService.request<unknown>(url, options);
            this.setResult(response);
            this.setStatus(`执行成功: ${operation.label}`, 'success');
        } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            this.setStatus(`执行失败: ${message}`, 'error');
            this.setResult({ error: message, operation: operation.label });
        } finally {
            this.setLoading(false);
        }
    }
}
