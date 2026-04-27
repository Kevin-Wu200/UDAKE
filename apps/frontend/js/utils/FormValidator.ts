/**
 * 表单实时验证系统
 * 支持即时验证、成功/警告/错误状态、可视化指示器
 */

import type { FormValidationRules, FieldState } from '../../types/core';
import { I18n } from "./I18n";

const t = (key: string, params?: Record<string, string | number>): string => I18n.t(key, params);

interface FieldEntry {
    input: HTMLInputElement;
    rules: FormValidationRules;
    state: FieldState;
    indicator?: HTMLSpanElement;
    message?: HTMLSpanElement;
}

export class FormValidator {
    fields: Map<string, FieldEntry>;
    onValidationChange: ((allValid: boolean) => void) | null;

    constructor() {
        this.fields = new Map();
        this.onValidationChange = null;
    }

    register(fieldId: string, rules: FormValidationRules): void {
        const input = document.getElementById(fieldId) as HTMLInputElement | null;
        if (!input) return;

        const field: FieldEntry = { input, rules, state: 'idle' };
        this.fields.set(fieldId, field);

        this._createValidationUI(field);

        input.addEventListener('input', () => this._validate(fieldId));
        input.addEventListener('blur', () => this._validate(fieldId));
    }

    _createValidationUI(field: FieldEntry): void {
        const input = field.input;
        const parent = input.parentElement!;

        parent.classList.add('form-field');

        let indicator = parent.querySelector('.field-indicator') as HTMLSpanElement | null;
        if (!indicator) {
            indicator = document.createElement('span');
            indicator.className = 'field-indicator';
            input.parentElement!.style.position = 'relative';
            input.after(indicator);
        }
        field.indicator = indicator;

        let msg = parent.querySelector('.field-message') as HTMLSpanElement | null;
        if (!msg) {
            msg = document.createElement('span');
            msg.className = 'field-message';
            indicator.after(msg);
        }
        field.message = msg;
    }

    _validate(fieldId: string): { valid: boolean } {
        const field = this.fields.get(fieldId);
        if (!field) return { valid: false };

        const { input, rules } = field;
        const value = input.value.trim();

        if (rules.required && value === '') {
            this._setState(field, 'error', rules.required);
            return { valid: false };
        }

        if (value === '' && !rules.required) {
            this._setState(field, 'idle', '');
            return { valid: true };
        }

        if (rules.pattern && !rules.pattern.test(value)) {
            this._setState(field, 'error', rules.patternMsg || t('formvalidator.error.format'));
            return { valid: false };
        }

        if (rules.custom) {
            const result = rules.custom(value);
            if (!result.valid) {
                this._setState(field, result.level || 'error', result.message);
                return { valid: false };
            }
            if (result.level === 'warning') {
                this._setState(field, 'warning', result.message);
                return { valid: true };
            }
        }

        this._setState(field, 'success', '');
        return { valid: true };
    }

    _setState(field: FieldEntry, state: FieldState, message?: string): void {
        const { input, indicator, message: msgEl } = field;
        const parent = input.parentElement!;

        parent.classList.remove('success', 'warning', 'error', 'idle');
        input.classList.remove('input-success', 'input-warning', 'input-error');

        field.state = state;

        if (state === 'idle') {
            indicator!.textContent = '';
            msgEl!.textContent = '';
            return;
        }

        parent.classList.add(state);

        const icons: Record<string, string> = { success: '✓', warning: '!', error: '✕' };
        indicator!.textContent = icons[state] || '';
        indicator!.className = `field-indicator field-indicator-${state}`;

        msgEl!.textContent = message || '';
        msgEl!.className = `field-message field-message-${state}`;

        if (this.onValidationChange) {
            this.onValidationChange(this.isAllValid());
        }
    }

    validateAll(): boolean {
        let allValid = true;
        for (const [fieldId] of this.fields) {
            const result = this._validate(fieldId);
            if (!result.valid) allValid = false;
        }
        return allValid;
    }

    isAllValid(): boolean {
        for (const [, field] of this.fields) {
            if (field.state === 'error') return false;
        }
        return true;
    }

    reset(): void {
        for (const [, field] of this.fields) {
            this._setState(field, 'idle', '');
        }
    }
}
