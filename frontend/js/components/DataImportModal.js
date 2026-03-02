/**
 * 数据导入配置弹窗组件
 * 显示坐标系统信息和字段映射选择
 */

import { FieldMatcher } from '../utils/fieldMatcher.js';
import { CoordinateTransformer } from '../utils/coordinateTransformer.js';

export class DataImportModal {
    constructor(onConfirm, view) {
        this.onConfirm = onConfirm;
        this.view = view;
        this.modal = null;
        this.parseResult = null;
        this.fieldSelection = {
            x: null,
            y: null,
            pointData: null
        };
    }

    /**
     * 显示弹窗
     * @param {Object} parseResult - GeoJSON 解析结果
     */
    show(parseResult) {
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

            this.animateIn();
            console.log('入场动画已触发');
        } catch (error) {
            console.error('显示弹窗时出错:', error);
            console.error('错误堆栈:', error.stack);
            throw error;
        }
    }

    /**
     * 创建弹窗
     */
    createModal() {
        try {
            console.log('createModal() 开始执行');
            console.log('parseResult:', this.parseResult);

            const modal = document.createElement('div');
            modal.className = 'modal-overlay';

            console.log('准备生成 HTML');
            const fieldOptions = this.renderFieldOptions();
            console.log('字段选项已生成');

            modal.innerHTML = `
                <div class="modal-content">
                    <h2 class="modal-title">数据字段配置</h2>

                    <!-- 坐标系统信息 -->
                    <div class="modal-section">
                        <h3 class="section-title">坐标系统信息</h3>
                        <div class="coordinate-info">
                            <div class="info-item">
                                <span class="info-label">投影坐标系</span>
                                <span class="info-value">${this.parseResult.crsInfo.projectedName}</span>
                            </div>
                            ${this.parseResult.crsInfo.projectedEPSG ? `
                            <div class="info-item">
                                <span class="info-label">投影 EPSG</span>
                                <span class="info-value">EPSG:${this.parseResult.crsInfo.projectedEPSG}</span>
                            </div>
                            ` : ''}
                            <div class="info-item">
                                <span class="info-label">地理坐标系</span>
                                <span class="info-value">${this.parseResult.crsInfo.geographicName}</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">地理 EPSG</span>
                                <span class="info-value">EPSG:${this.parseResult.crsInfo.geographicEPSG}</span>
                            </div>
                        </div>
                    </div>

                    <!-- 字段映射选择 -->
                    <div class="modal-section">
                        <h3 class="section-title">字段映射选择</h3>
                        <div class="field-mapping">
                            <div class="form-group">
                                <label>X 字段</label>
                                <select id="field-x" class="select">
                                    <option value="">请选择</option>
                                    ${fieldOptions}
                                </select>
                                <span class="error-message" id="error-field-x"></span>
                            </div>
                            <div class="form-group">
                                <label>Y 字段</label>
                                <select id="field-y" class="select">
                                    <option value="">请选择</option>
                                    ${fieldOptions}
                                </select>
                                <span class="error-message" id="error-field-y"></span>
                            </div>
                            <div class="form-group">
                                <label>Point_Data 字段</label>
                                <select id="field-point-data" class="select">
                                    <option value="">请选择</option>
                                    ${fieldOptions}
                                </select>
                                <span class="error-message" id="error-field-point-data"></span>
                            </div>
                        </div>
                    </div>

                    <!-- 操作按钮 -->
                    <div class="modal-actions">
                        <button id="modal-cancel" class="btn btn-secondary">取消</button>
                        <button id="modal-confirm" class="btn btn-primary">确认导入</button>
                    </div>
                </div>
            `;

            console.log('弹窗 HTML 已生成');
            document.body.appendChild(modal);
            console.log('弹窗已添加到 body');
            console.log('body 子元素数量:', document.body.children.length);
            this.modal = modal;
        } catch (error) {
            console.error('创建弹窗时出错:', error);
            console.error('错误堆栈:', error.stack);
            throw error;
        }
    }

    /**
     * 渲染字段选项
     */
    renderFieldOptions() {
        console.log('renderFieldOptions() 被调用');
        console.log('可用字段:', this.parseResult.fields);

        if (!this.parseResult.fields || this.parseResult.fields.length === 0) {
            console.warn('没有可用字段');
            return '';
        }

        const options = this.parseResult.fields
            .map(field => `<option value="${field}">${field}</option>`)
            .join('');

        console.log('生成的选项:', options);
        return options;
    }

    /**
     * 自动匹配字段
     */
    autoMatchFields() {
        try {
            console.log('autoMatchFields() 开始执行');
            console.log('可用字段:', this.parseResult.fields);

            const matched = FieldMatcher.matchFields(this.parseResult.fields);
            console.log('匹配结果:', matched);

            if (matched.x) {
                const fieldX = this.modal.querySelector('#field-x');
                console.log('找到 X 字段选择器:', fieldX);
                if (fieldX) {
                    fieldX.value = matched.x;
                    this.fieldSelection.x = matched.x;
                    console.log('已设置 X 字段:', matched.x);
                }
            }

            if (matched.y) {
                const fieldY = this.modal.querySelector('#field-y');
                console.log('找到 Y 字段选择器:', fieldY);
                if (fieldY) {
                    fieldY.value = matched.y;
                    this.fieldSelection.y = matched.y;
                    console.log('已设置 Y 字段:', matched.y);
                }
            }

            if (matched.pointData) {
                const fieldPointData = this.modal.querySelector('#field-point-data');
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
            console.error('错误堆栈:', error.stack);
        }
    }

    /**
     * 绑定事件
     */
    bindEvents() {
        try {
            console.log('bindEvents() 开始执行');

            // 字段选择
            this.modal.querySelector('#field-x').addEventListener('change', (e) => {
                this.fieldSelection.x = e.target.value;
                this.clearError('field-x');
            });

            this.modal.querySelector('#field-y').addEventListener('change', (e) => {
                this.fieldSelection.y = e.target.value;
                this.clearError('field-y');
            });

            this.modal.querySelector('#field-point-data').addEventListener('change', (e) => {
                this.fieldSelection.pointData = e.target.value;
                this.clearError('field-point-data');
            });

            // 取消按钮
            this.modal.querySelector('#modal-cancel').addEventListener('click', () => {
                this.close();
            });

            // 确认按钮
            this.modal.querySelector('#modal-confirm').addEventListener('click', () => {
                this.handleConfirm();
            });

            // 点击背景关闭
            this.modal.addEventListener('click', (e) => {
                if (e.target === this.modal) {
                    this.close();
                }
            });

            console.log('bindEvents() 执行完成');
        } catch (error) {
            console.error('绑定事件时出错:', error);
            console.error('错误堆栈:', error.stack);
        }
    }

    /**
     * 处理确认
     */
    async handleConfirm() {
        // 验证字段选择
        const validation = FieldMatcher.validateSelection(this.fieldSelection);

        if (!validation.valid) {
            this.showErrors(validation.errors);
            return;
        }

        // 验证 point_data 是否为数值
        if (!FieldMatcher.isNumericField(this.parseResult.geojson, this.fieldSelection.pointData)) {
            this.showError('field-point-data', 'point_data 必须为数值类型');
            return;
        }

        try {
            // 转换数据
            const transformedData = await this.transformData();

            // 回调
            if (this.onConfirm) {
                this.onConfirm(transformedData);
            }

            // 关闭弹窗
            this.close();

        } catch (error) {
            console.error('数据转换失败:', error);
            this.showError('field-x', error.message);
        }
    }

    /**
     * 转换数据
     */
    async transformData() {
        const features = this.parseResult.geojson.features;
        const data = [];

        for (const feature of features) {
            const props = feature.properties;
            const coords = feature.geometry.coordinates;

            let x = props[this.fieldSelection.x] || coords[0];
            let y = props[this.fieldSelection.y] || coords[1];
            const value = parseFloat(props[this.fieldSelection.pointData]);

            // 检测是否为经纬度
            if (CoordinateTransformer.isGeographic(x, y)) {
                try {
                    // 转换为当前地图投影
                    const transformed = await CoordinateTransformer.transformPoint(
                        x, y,
                        CoordinateTransformer.WGS84,
                        this.view.spatialReference
                    );

                    x = transformed.x;
                    y = transformed.y;
                } catch (error) {
                    throw new Error('坐标转换失败');
                }
            }

            data.push({ x, y, value });
        }

        return {
            data,
            geojson: this.parseResult.geojson,
            fieldMapping: this.fieldSelection
        };
    }

    /**
     * 显示错误
     */
    showError(fieldId, message) {
        const select = this.modal.querySelector(`#${fieldId}`);
        const errorSpan = this.modal.querySelector(`#error-${fieldId}`);

        select.style.borderColor = '#ff453a';
        select.style.transition = 'border-color 200ms';
        errorSpan.textContent = message;
        errorSpan.style.display = 'block';
    }

    /**
     * 显示多个错误
     */
    showErrors(errors) {
        if (errors.x) this.showError('field-x', errors.x);
        if (errors.y) this.showError('field-y', errors.y);
        if (errors.pointData) this.showError('field-point-data', errors.pointData);
    }

    /**
     * 清除错误
     */
    clearError(fieldId) {
        const select = this.modal.querySelector(`#${fieldId}`);
        const errorSpan = this.modal.querySelector(`#error-${fieldId}`);

        select.style.borderColor = '';
        errorSpan.textContent = '';
        errorSpan.style.display = 'none';
    }

    /**
     * 入场动画
     */
    animateIn() {
        console.log('animateIn() 被调用');
        console.log('弹窗元素:', this.modal);

        // 确保 DOM 已经渲染
        requestAnimationFrame(() => {
            console.log('requestAnimationFrame 回调执行');
            this.modal.classList.add('modal-show');
            console.log('已添加 modal-show 类');
            console.log('弹窗类名:', this.modal.className);
        });
    }

    /**
     * 关闭弹窗
     */
    close() {
        this.modal.classList.remove('modal-show');
        setTimeout(() => {
            if (this.modal && this.modal.parentNode) {
                this.modal.parentNode.removeChild(this.modal);
            }
            this.modal = null;
        }, 250);
    }
}
