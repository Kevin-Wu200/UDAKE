import { describe, it, expect, beforeEach } from 'vitest';
import { FormValidator } from '../frontend/js/utils/FormValidator.js';

describe('FormValidator', () => {
    let validator;

    beforeEach(() => {
        // 创建测试 DOM
        document.body.innerHTML = `
            <div class="form-group">
                <input id="test-field" class="input" value="">
            </div>
            <div class="form-group">
                <input id="number-field" class="input" value="">
            </div>
        `;
        validator = new FormValidator();
    });

    describe('注册和基本验证', () => {
        it('应该成功注册字段', () => {
            validator.register('test-field', { required: '必填' });
            expect(validator.fields.has('test-field')).toBe(true);
        });

        it('注册不存在的字段应该静默失败', () => {
            validator.register('nonexistent', { required: '必填' });
            expect(validator.fields.has('nonexistent')).toBe(false);
        });

        it('应该创建验证 UI 元素', () => {
            validator.register('test-field', { required: '必填' });
            const parent = document.getElementById('test-field').parentElement;
            expect(parent.classList.contains('form-field')).toBe(true);
            expect(parent.querySelector('.field-indicator')).not.toBeNull();
            expect(parent.querySelector('.field-message')).not.toBeNull();
        });
    });

    describe('必填验证', () => {
        it('空值应该返回错误', () => {
            validator.register('test-field', { required: '请输入内容' });
            const input = document.getElementById('test-field');
            input.value = '';
            input.dispatchEvent(new Event('input'));

            const field = validator.fields.get('test-field');
            expect(field.state).toBe('error');
        });

        it('有值应该通过验证', () => {
            validator.register('test-field', { required: '请输入内容' });
            const input = document.getElementById('test-field');
            input.value = 'hello';
            input.dispatchEvent(new Event('input'));

            const field = validator.fields.get('test-field');
            expect(field.state).toBe('success');
        });
    });

    describe('正则验证', () => {
        it('不匹配正则应该返回错误', () => {
            validator.register('test-field', {
                pattern: /^\d+$/,
                patternMsg: '只能输入数字'
            });
            const input = document.getElementById('test-field');
            input.value = 'abc';
            input.dispatchEvent(new Event('input'));

            const field = validator.fields.get('test-field');
            expect(field.state).toBe('error');
        });

        it('匹配正则应该通过', () => {
            validator.register('test-field', {
                pattern: /^\d+$/,
                patternMsg: '只能输入数字'
            });
            const input = document.getElementById('test-field');
            input.value = '123';
            input.dispatchEvent(new Event('input'));

            const field = validator.fields.get('test-field');
            expect(field.state).toBe('success');
        });
    });

    describe('自定义验证', () => {
        it('自定义验证失败应该返回错误', () => {
            validator.register('number-field', {
                custom: (value) => {
                    const num = parseInt(value, 10);
                    if (num > 100) return { valid: false, message: '不能超过100', level: 'error' };
                    return { valid: true };
                }
            });
            const input = document.getElementById('number-field');
            input.value = '200';
            input.dispatchEvent(new Event('input'));

            const field = validator.fields.get('number-field');
            expect(field.state).toBe('error');
        });

        it('自定义验证警告应该设置 warning 状态', () => {
            validator.register('number-field', {
                custom: (value) => {
                    const num = parseInt(value, 10);
                    if (num > 50) return { valid: true, message: '值较大', level: 'warning' };
                    return { valid: true };
                }
            });
            const input = document.getElementById('number-field');
            input.value = '80';
            input.dispatchEvent(new Event('input'));

            const field = validator.fields.get('number-field');
            expect(field.state).toBe('warning');
        });
    });

    describe('全局验证', () => {
        it('validateAll 应该验证所有字段', () => {
            validator.register('test-field', { required: '必填' });
            validator.register('number-field', { required: '必填' });

            document.getElementById('test-field').value = 'ok';
            document.getElementById('number-field').value = '';

            expect(validator.validateAll()).toBe(false);
        });

        it('isAllValid 应该检查所有字段状态', () => {
            validator.register('test-field', { required: '必填' });
            const input = document.getElementById('test-field');
            input.value = 'ok';
            input.dispatchEvent(new Event('input'));

            expect(validator.isAllValid()).toBe(true);
        });

        it('reset 应该重置所有字段状态', () => {
            validator.register('test-field', { required: '必填' });
            const input = document.getElementById('test-field');
            input.value = '';
            input.dispatchEvent(new Event('input'));

            validator.reset();
            const field = validator.fields.get('test-field');
            expect(field.state).toBe('idle');
        });
    });

    describe('回调通知', () => {
        it('onValidationChange 应该在状态变化时被调用', () => {
            let lastResult = null;
            validator.onValidationChange = (allValid) => { lastResult = allValid; };

            validator.register('test-field', { required: '必填' });
            const input = document.getElementById('test-field');
            input.value = 'ok';
            input.dispatchEvent(new Event('input'));

            expect(lastResult).toBe(true);
        });
    });
});
