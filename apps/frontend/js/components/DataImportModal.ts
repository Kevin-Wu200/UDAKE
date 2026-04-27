/**
 * 数据导入配置弹窗组件
 * 显示坐标系统信息和字段映射选择
 */

import { FieldMatcher } from '../utils/fieldMatcher.js';
import { CoordinateTransformer } from '../utils/coordinateTransformer.js';
import { KeyboardManager } from '../utils/KeyboardManager.js';
import { I18n } from '../utils/I18n.js';

interface CRSInfo {
    projectedName: string;
    projectedEPSG?: string;
    geographicName: string;
    geographicEPSG: string;
}

interface ParseResult {
    fields: string[];
    geojson: any;
    crsInfo: CRSInfo;
}

interface FieldSelection {
    x: string | null;
    y: string | null;
    pointData: string | null;
}

interface FieldErrorStateItem {
    key: string | null;
    message: string | null;
}

interface FieldErrorState {
    x: FieldErrorStateItem;
    y: FieldErrorStateItem;
    pointData: FieldErrorStateItem;
}

interface TransformedData {
    data: Array<{ x: number; y: number; value: number }>;
    geojson: any;
    fieldMapping: FieldSelection;
}

export class DataImportModal {
    onConfirm: ((data: TransformedData) => void) | null;
    view: any;
    modal: HTMLDivElement | null;
    parseResult: ParseResult | null;
    _releaseFocusTrap: (() => void) | null;
    _unsubscribeLocaleChange: (() => void) | null;
    fieldSelection: FieldSelection;
    fieldErrors: FieldErrorState;

    constructor(onConfirm: ((data: TransformedData) => void) | null, view: any) {
        this.onConfirm = onConfirm;
        this.view = view;
        this.modal = null;
        this.parseResult = null;
        this._releaseFocusTrap = null;
        this._unsubscribeLocaleChange = null;
        this.fieldSelection = {
            x: null,
            y: null,
            pointData: null
        };
        this.fieldErrors = this.createEmptyFieldErrors();
    }

    show(parseResult: ParseResult): void {
        try {
            console.log('DataImportModal.show() 被调用');
            console.log('解析结果:', parseResult);

            this.parseResult = parseResult;
            this.createModal();
            console.log('弹窗 DOM 已创建');

            this.autoMatchFields();
            console.log('字段自动匹配完成');

            this.bindEvents();
            console.log('事件绑定完成');

            this.subscribeToLocaleChange();
            console.log('语言切换监听已绑定');

            this.animateIn();
            console.log('入场动画已触发');
        } catch (error) {
            console.error('显示弹窗时出错:', error);
            console.error('错误堆栈:', (error as Error).stack);
            throw error;
        }
    }

    createEmptyFieldErrors(): FieldErrorState {
        return {
            x: { key: null, message: null },
            y: { key: null, message: null },
            pointData: { key: null, message: null }
        };
    }

    createModal(): void {
        try {
            console.log('createModal() 开始执行');
            console.log('parseResult:', this.parseResult);

            const modal = document.createElement('div');
            modal.className = 'modal-overlay';
            this.renderModalContent(modal);

            console.log('弹窗 HTML 已生成');
            document.body.appendChild(modal);
            console.log('弹窗已添加到 body');
            console.log('body 子元素数量:', document.body.children.length);
            this.modal = modal;
        } catch (error) {
            console.error('创建弹窗时出错:', error);
            console.error('错误堆栈:', (error as Error).stack);
            throw error;
        }
    }

    renderModalContent(modal: HTMLDivElement): void {
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-modal', 'true');
        modal.setAttribute('aria-label', I18n.t('dataimport.modal.aria_label'));

        const fieldOptions = this.renderFieldOptions();

        modal.innerHTML = `
            <div class="modal-content">
                <h2 class="modal-title">${I18n.t('dataimport.title')}</h2>

                <!-- 坐标系统信息 -->
                <div class="modal-section">
                    <h3 class="section-title">${I18n.t('dataimport.section.coordinate_system')}</h3>
                    <div class="coordinate-info">
                        <div class="info-item">
                            <span class="info-label">${I18n.t('dataimport.label.projected_coordinate_system')}</span>
                            <span class="info-value">${this.parseResult!.crsInfo.projectedName}</span>
                        </div>
                        ${this.parseResult!.crsInfo.projectedEPSG ? `
                        <div class="info-item">
                            <span class="info-label">${I18n.t('dataimport.label.projected_epsg')}</span>
                            <span class="info-value">EPSG:${this.parseResult!.crsInfo.projectedEPSG}</span>
                        </div>
                        ` : ''}
                        <div class="info-item">
                            <span class="info-label">${I18n.t('dataimport.label.geographic_coordinate_system')}</span>
                            <span class="info-value">${this.parseResult!.crsInfo.geographicName}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">${I18n.t('dataimport.label.geographic_epsg')}</span>
                            <span class="info-value">EPSG:${this.parseResult!.crsInfo.geographicEPSG}</span>
                        </div>
                    </div>
                </div>

                <!-- 字段映射选择 -->
                <div class="modal-section">
                    <h3 class="section-title">${I18n.t('dataimport.section.field_mapping')}</h3>
                    <div class="field-mapping">
                        <div class="form-group">
                            <label for="field-x">${I18n.t('dataimport.field.x')}</label>
                            <select id="field-x" class="select">
                                <option value="">${I18n.t('dataimport.option.select')}</option>
                                ${fieldOptions}
                            </select>
                            <span class="error-message" id="error-field-x" role="alert"></span>
                        </div>
                        <div class="form-group">
                            <label for="field-y">${I18n.t('dataimport.field.y')}</label>
                            <select id="field-y" class="select">
                                <option value="">${I18n.t('dataimport.option.select')}</option>
                                ${fieldOptions}
                            </select>
                            <span class="error-message" id="error-field-y" role="alert"></span>
                        </div>
                        <div class="form-group">
                            <label for="field-point-data">${I18n.t('dataimport.field.point_data')}</label>
                            <select id="field-point-data" class="select">
                                <option value="">${I18n.t('dataimport.option.select')}</option>
                                ${fieldOptions}
                            </select>
                            <span class="error-message" id="error-field-point-data" role="alert"></span>
                        </div>
                    </div>
                </div>

                <!-- 操作按钮 -->
                <div class="modal-actions">
                    <button id="modal-cancel" class="btn btn-secondary">${I18n.t('common.cancel')}</button>
                    <button id="modal-confirm" class="btn btn-primary">${I18n.t('dataimport.action.confirmimport')}</button>
                </div>
            </div>
        `;
    }

    renderFieldOptions(): string {
        console.log('renderFieldOptions() 被调用');
        console.log('可用字段:', this.parseResult!.fields);

        if (!this.parseResult!.fields || this.parseResult!.fields.length === 0) {
            console.warn('没有可用字段');
            return '';
        }

        const options = this.parseResult!.fields
            .map(field => `<option value="${field}">${field}</option>`)
            .join('');

        console.log('生成的选项:', options);
        return options;
    }

    autoMatchFields(): void {
        try {
            console.log('autoMatchFields() 开始执行');
            console.log('可用字段:', this.parseResult!.fields);

            const matched: any = FieldMatcher.matchFields(this.parseResult!.fields);
            console.log('匹配结果:', matched);

            if (matched.x) {
                const fieldX = this.modal!.querySelector('#field-x') as HTMLSelectElement;
                console.log('找到 X 字段选择器:', fieldX);
                if (fieldX) {
                    fieldX.value = matched.x;
                    this.fieldSelection.x = matched.x;
                    console.log('已设置 X 字段:', matched.x);
                }
            }

            if (matched.y) {
                const fieldY = this.modal!.querySelector('#field-y') as HTMLSelectElement;
                console.log('找到 Y 字段选择器:', fieldY);
                if (fieldY) {
                    fieldY.value = matched.y;
                    this.fieldSelection.y = matched.y;
                    console.log('已设置 Y 字段:', matched.y);
                }
            }

            if (matched.pointData) {
                const fieldPointData = this.modal!.querySelector('#field-point-data') as HTMLSelectElement;
                console.log('找到 Point_Data 字段选择器:', fieldPointData);
                if (fieldPointData) {
                    fieldPointData.value = matched.pointData;
                    this.fieldSelection.pointData = matched.pointData;
                    console.log('已设置 Point_Data 字段:', matched.pointData);
                }
            }

            console.log('autoMatchFields() 执行完成');
        } catch (error) {
            console.error('自动匹配字段时出错:', error);
            console.error('错误堆栈:', (error as Error).stack);
        }
    }

    bindEvents(): void {
        try {
            console.log('bindEvents() 开始执行');

            this.modal!.addEventListener('click', (e: MouseEvent) => {
                if (e.target === this.modal) {
                    this.close();
                }
            });

            this.modal!.addEventListener('keydown', (e: KeyboardEvent) => {
                if (e.key === 'Escape') {
                    this.close();
                }
            });

            this.bindFieldEvents();

            console.log('bindEvents() 执行完成');
        } catch (error) {
            console.error('绑定事件时出错:', error);
            console.error('错误堆栈:', (error as Error).stack);
        }
    }

    bindFieldEvents(): void {
        try {
            this.modal!.querySelector('#field-x')!.addEventListener('change', (e: Event) => {
                this.fieldSelection.x = (e.target as HTMLSelectElement).value;
                this.clearError('field-x');
            });

            this.modal!.querySelector('#field-y')!.addEventListener('change', (e: Event) => {
                this.fieldSelection.y = (e.target as HTMLSelectElement).value;
                this.clearError('field-y');
            });

            this.modal!.querySelector('#field-point-data')!.addEventListener('change', (e: Event) => {
                this.fieldSelection.pointData = (e.target as HTMLSelectElement).value;
                this.clearError('field-point-data');
            });

            this.modal!.querySelector('#modal-cancel')!.addEventListener('click', () => {
                this.close();
            });

            this.modal!.querySelector('#modal-confirm')!.addEventListener('click', () => {
                this.handleConfirm();
            });
        } catch (error) {
            console.error('绑定字段事件时出错:', error);
            console.error('错误堆栈:', (error as Error).stack);
        }
    }

    subscribeToLocaleChange(): void {
        if (this._unsubscribeLocaleChange) {
            return;
        }

        this._unsubscribeLocaleChange = I18n.onChange(() => {
            this.refreshLocale();
        });
    }

    refreshLocale(): void {
        if (!this.modal || !this.parseResult) {
            return;
        }

        const currentSelection = { ...this.fieldSelection };

        this.renderModalContent(this.modal);
        this.fieldSelection = currentSelection;
        this.restoreFieldSelection();
        this.bindFieldEvents();
        this.restoreErrors();
    }

    restoreFieldSelection(): void {
        if (!this.modal) {
            return;
        }

        const fieldX = this.modal.querySelector('#field-x') as HTMLSelectElement | null;
        const fieldY = this.modal.querySelector('#field-y') as HTMLSelectElement | null;
        const fieldPointData = this.modal.querySelector('#field-point-data') as HTMLSelectElement | null;

        if (fieldX) {
            fieldX.value = this.fieldSelection.x || '';
        }
        if (fieldY) {
            fieldY.value = this.fieldSelection.y || '';
        }
        if (fieldPointData) {
            fieldPointData.value = this.fieldSelection.pointData || '';
        }
    }

    restoreErrors(): void {
        const restoreFieldError = (fieldId: keyof FieldSelection, elementId: string): void => {
            const error = this.fieldErrors[fieldId];
            if (!error.message && !error.key) {
                return;
            }

            this.showError(elementId, error.key ? I18n.t(error.key) : error.message!, error.key || undefined);
        };

        restoreFieldError('x', 'field-x');
        restoreFieldError('y', 'field-y');
        restoreFieldError('pointData', 'field-point-data');
    }

    async handleConfirm(): Promise<void> {
        const validation: any = FieldMatcher.validateSelection(this.fieldSelection);

        if (!validation.valid) {
            this.showErrors(validation.errors);
            return;
        }

        if (!FieldMatcher.isNumericField(this.parseResult!.geojson, this.fieldSelection.pointData!)) {
            this.showError(
                'field-point-data',
                I18n.t('dataimport.error.point_data_numeric'),
                'dataimport.error.point_data_numeric'
            );
            return;
        }

        try {
            const transformedData = await this.transformData();

            if (this.onConfirm) {
                this.onConfirm(transformedData);
            }

            this.close();

        } catch (error) {
            console.error('数据转换失败:', error);
            this.showError('field-x', (error as Error).message);
        }
    }

    async transformData(): Promise<TransformedData> {
        const features = this.parseResult!.geojson.features;
        const data: Array<{ x: number; y: number; value: number }> = [];

        for (const feature of features) {
            const props = feature.properties;
            const coords = feature.geometry.coordinates;

            let x: number = props[this.fieldSelection.x!] || coords[0];
            let y: number = props[this.fieldSelection.y!] || coords[1];
            const value: number = parseFloat(props[this.fieldSelection.pointData!]);

            if (CoordinateTransformer.isGeographic(x, y)) {
                try {
                    const transformed: any = await CoordinateTransformer.transformPoint(
                        x, y,
                        CoordinateTransformer.WGS84,
                        this.view.spatialReference
                    );

                    x = transformed.x;
                    y = transformed.y;
                } catch (error) {
                    throw new Error(I18n.t('dataimport.error.coordinate_transform_failed'));
                }
            }

            data.push({ x, y, value });
        }

        return {
            data,
            geojson: this.parseResult!.geojson,
            fieldMapping: this.fieldSelection
        };
    }

    showError(fieldId: string, message: string, translationKey?: string): void {
        const select = this.modal!.querySelector(`#${fieldId}`) as HTMLSelectElement;
        const errorSpan = this.modal!.querySelector(`#error-${fieldId}`) as HTMLSpanElement;
        const stateKey = this.toFieldStateKey(fieldId);

        select.style.borderColor = '#ff453a';
        select.style.transition = 'border-color 200ms';
        errorSpan.textContent = message;
        errorSpan.style.display = 'block';
        this.fieldErrors[stateKey] = {
            key: translationKey || null,
            message
        };
    }

    showErrors(errors: Record<string, string>): void {
        if (errors.x) this.showError('field-x', errors.x, 'dataimport.validation.select_x');
        if (errors.y) this.showError('field-y', errors.y, 'dataimport.validation.select_y');
        if (errors.pointData) this.showError('field-point-data', errors.pointData, 'dataimport.validation.select_point_data');
    }

    clearError(fieldId: string): void {
        const select = this.modal!.querySelector(`#${fieldId}`) as HTMLSelectElement;
        const errorSpan = this.modal!.querySelector(`#error-${fieldId}`) as HTMLSpanElement;

        select.style.borderColor = '';
        errorSpan.textContent = '';
        errorSpan.style.display = 'none';
        this.fieldErrors[this.toFieldStateKey(fieldId)] = {
            key: null,
            message: null
        };
    }

    toFieldStateKey(fieldId: string): keyof FieldSelection {
        if (fieldId === 'field-x') {
            return 'x';
        }
        if (fieldId === 'field-y') {
            return 'y';
        }
        return 'pointData';
    }

    animateIn(): void {
        console.log('animateIn() 被调用');

        requestAnimationFrame(() => {
            this.modal!.classList.add('modal-show');
            this._releaseFocusTrap = KeyboardManager.trapFocus(this.modal!);
        });
    }

    close(): void {
        if (this._unsubscribeLocaleChange) {
            this._unsubscribeLocaleChange();
            this._unsubscribeLocaleChange = null;
        }
        if (this._releaseFocusTrap) {
            this._releaseFocusTrap();
            this._releaseFocusTrap = null;
        }
        this.modal!.classList.remove('modal-show');
        setTimeout(() => {
            if (this.modal && this.modal.parentNode) {
                this.modal.parentNode.removeChild(this.modal);
            }
            this.modal = null;
            this.fieldErrors = this.createEmptyFieldErrors();
        }, 250);
    }
}
