/**
 * 行业选择组件
 * 提供行业类型选择和参数推荐功能
 */

import { TemplateDownloader } from './TemplateDownloader';
import { I18n } from '../utils/I18n.js';

interface IndustryConfig {
  industry: string;
  name: string;
  description: string;
  default_method: string;
  default_variogram: string;
  default_grid_resolution: number;
  default_nlags: number;
  enable_anisotropy: boolean;
  enable_trend_detection: boolean;
  max_range?: number;
  nugget_ratio?: number;
  custom_parameters: Record<string, any>;
  template_filename: string;
}

interface IndustryRecommendation {
  industry: string;
  industry_name: string;
  recommended_method: string;
  recommended_variogram: string;
  recommended_grid_resolution: number;
  recommended_nlags: number;
  enable_anisotropy: boolean;
  enable_trend_detection: boolean;
  custom_parameters: Record<string, any>;
  template_available: boolean;
  template_filename: string;
  message: string;
}

export class IndustrySelector {
  private container: HTMLElement;
  private industries: IndustryConfig[] = [];
  private selectedIndustry: IndustryConfig | null = null;
  private onIndustrySelect: ((industry: IndustryConfig) => void) | null = null;
  private onTemplateDownload: ((template: string) => void) | null = null;
  private currentDataId: string = '';
  private apiURL: string;

  constructor(container: HTMLElement | string, apiURL: string = '/api') {
    this.container = typeof container === 'string'
      ? document.querySelector(container)!
      : container;
    this.apiURL = apiURL;
    this.init();
  }

  private init(): void {
    this.render();
    this.loadIndustries();
    this.bindEvents();
  }

  private async loadIndustries(): Promise<void> {
    const maxRetries = 8;
    const retryDelay = 2000; // 2秒

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        console.log(`正在加载行业配置（尝试 ${attempt}/${maxRetries}）... URL: ${this.apiURL}/industries`);
        const response = await fetch(`${this.apiURL}/industries`);
        const data = await response.json();
        this.industries = data.industries;
        this.renderIndustryOptions();
        console.log(`✓ 成功加载 ${this.industries.length} 个行业配置`);
        return;
      } catch (error) {
        console.error(`加载行业配置失败（尝试 ${attempt}/${maxRetries}）:`, error);
        if (attempt < maxRetries) {
          await new Promise(resolve => setTimeout(resolve, retryDelay));
        } else {
          console.error('加载行业配置失败: 已达到最大重试次数');
          // 显示错误提示
          const container = this.container.querySelector('.industry-selector') as HTMLElement;
          if (container) {
            const errorMessage = document.createElement('div');
            errorMessage.className = 'error-message';
            errorMessage.textContent = I18n.t('recommendation.error');
            errorMessage.style.cssText = 'color: #ff3b30; padding: 12px; background: rgba(255, 59, 48, 0.1); border-radius: 8px; margin-top: 12px;';
            container.appendChild(errorMessage);
          }
        }
      }
    }
  }

  private render(): void {
    this.container.innerHTML = `
      <div class="industry-selector">
        <div class="industry-header">
          <h3 data-i18n="industry.title">${I18n.t('industry.title')}</h3>
          <p class="industry-description" data-i18n="industry.description">${I18n.t('industry.description')}</p>
        </div>

        <div class="industry-input-group">
          <label for="data-id" data-i18n="industry.dataId">${I18n.t('industry.dataId')}</label>
          <input
            type="text"
            id="data-id"
            class="industry-input"
            placeholder="${I18n.t('industry.dataId')}"
          />
          <div class="input-hint" data-i18n="industry.dataIdHint">
            ${I18n.t('industry.dataIdHint')}
          </div>
        </div>

        <div class="industry-input-group">
          <label for="industry-select" data-i18n="industry.select">${I18n.t('industry.select')}</label>
          <select id="industry-select" class="industry-select">
            <option value="">${I18n.t('industry.placeholder')}</option>
          </select>
        </div>

        <div class="industry-actions">
          <button id="recommend-btn" class="industry-btn recommend-btn" disabled>
            ${I18n.t('industry.getRecommendation')}
          </button>
          <button id="download-template-btn" class="industry-btn template-btn" disabled>
            ${I18n.t('industry.downloadTemplate')}
          </button>
        </div>

        <div id="recommendation-panel" class="recommendation-panel hidden">
          <h4 data-i18n="industry.recommendationTitle">${I18n.t('industry.recommendationTitle')}</h4>
          <div class="recommendation-content"></div>
        </div>

        <div id="template-dialog" class="template-dialog hidden">
          <div class="template-dialog-content">
            <h4 data-i18n="template.downloadDialog">${I18n.t('template.downloadDialog')}</h4>
            <p class="template-description"></p>
            <div class="template-actions">
              <button class="template-dialog-btn confirm-btn" data-i18n="common.confirm">${I18n.t('common.confirm')}</button>
              <button class="template-dialog-btn cancel-btn" data-i18n="common.cancel">${I18n.t('common.cancel')}</button>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  private renderIndustryOptions(): void {
    const select = this.container.querySelector('#industry-select') as HTMLSelectElement;
    select.innerHTML = `<option value="">${I18n.t('industry.placeholder')}</option>`;

    this.industries.forEach(industry => {
      const option = document.createElement('option');
      option.value = industry.industry;
      option.textContent = I18n.getIndustryName(industry.industry);
      select.appendChild(option);
    });
  }

  /** 更新界面文本（用于语言切换） */
  public updateUIText(): void {
    if (!this.container) return;

    // 更新标题
    const title = this.container.querySelector('.industry-header h3');
    if (title) {
      title.textContent = I18n.t('industry.title');
    }

    const description = this.container.querySelector('.industry-description');
    if (description) {
      description.textContent = I18n.t('industry.description');
    }

    // 更新标签
    const dataIdLabel = this.container.querySelector('label[for="data-id"]');
    if (dataIdLabel) {
      dataIdLabel.textContent = I18n.t('industry.dataId');
    }

    const industrySelectLabel = this.container.querySelector('label[for="industry-select"]');
    if (industrySelectLabel) {
      industrySelectLabel.textContent = I18n.t('industry.select');
    }

    // 更新提示
    const dataIdHint = this.container.querySelector('.input-hint');
    if (dataIdHint) {
      dataIdHint.textContent = I18n.t('industry.dataIdHint');
    }

    // 更新按钮
    const recommendBtn = this.container.querySelector('#recommend-btn');
    if (recommendBtn) {
      recommendBtn.textContent = I18n.t('industry.getRecommendation');
    }

    const downloadTemplateBtn = this.container.querySelector('#download-template-btn');
    if (downloadTemplateBtn) {
      downloadTemplateBtn.textContent = I18n.t('industry.downloadTemplate');
    }

    // 更新输入框占位符
    const dataIdInput = this.container.querySelector('#data-id') as HTMLInputElement;
    if (dataIdInput) {
      dataIdInput.placeholder = I18n.t('industry.dataId');
    }

    // 重新渲染行业选项
    this.renderIndustryOptions();

    // 更新模板对话框
    const confirmBtn = this.container.querySelector('.confirm-btn');
    if (confirmBtn) {
      confirmBtn.textContent = I18n.t('common.confirm');
    }

    const cancelBtn = this.container.querySelector('.cancel-btn');
    if (cancelBtn) {
      cancelBtn.textContent = I18n.t('common.cancel');
    }

    // 更新推荐标题
    const recommendationTitle = this.container.querySelector('#recommendation-panel h4');
    if (recommendationTitle) {
      recommendationTitle.textContent = I18n.t('industry.recommendationTitle');
    }
  }

  private bindEvents(): void {
    const dataIdInput = this.container.querySelector('#data-id') as HTMLInputElement;
    const industrySelect = this.container.querySelector('#industry-select') as HTMLSelectElement;
    const recommendBtn = this.container.querySelector('#recommend-btn') as HTMLButtonElement;
    const downloadTemplateBtn = this.container.querySelector('#download-template-btn') as HTMLButtonElement;
    const confirmBtn = this.container.querySelector('.confirm-btn') as HTMLButtonElement;
    const cancelBtn = this.container.querySelector('.cancel-btn') as HTMLButtonElement;

    // 数据ID输入
    dataIdInput.addEventListener('input', (e) => {
      this.currentDataId = (e.target as HTMLInputElement).value;
      this.updateButtons();
    });

    // 行业选择
    industrySelect.addEventListener('change', (e) => {
      const industryValue = (e.target as HTMLSelectElement).value;
      this.selectedIndustry = this.industries.find(i => i.industry === industryValue) || null;
      this.updateButtons();
      this.showIndustryDescription();
    });

    // 获取推荐参数
    recommendBtn.addEventListener('click', () => {
      this.getRecommendation();
    });

    // 下载模板
    downloadTemplateBtn.addEventListener('click', () => {
      if (this.selectedIndustry && this.onTemplateDownload) {
        this.showTemplateDialog(this.selectedIndustry);
      }
    });

    // 模板下载确认
    confirmBtn.addEventListener('click', () => {
      if (this.selectedIndustry) {
        this.downloadTemplate(this.selectedIndustry.template_filename);
        this.hideTemplateDialog();
      }
    });

    // 模板下载取消
    cancelBtn.addEventListener('click', () => {
      this.hideTemplateDialog();
    });
  }

  private updateButtons(): void {
    const recommendBtn = this.container.querySelector('#recommend-btn') as HTMLButtonElement;
    const downloadTemplateBtn = this.container.querySelector('#download-template-btn') as HTMLButtonElement;

    const canRecommend = this.currentDataId && this.selectedIndustry;
    recommendBtn.disabled = !canRecommend;
    downloadTemplateBtn.disabled = !this.selectedIndustry;
  }

  private showIndustryDescription(): void {
    if (!this.selectedIndustry) return;

    const description = this.container.querySelector('.industry-description') as HTMLElement;
    const industryName = I18n.getIndustryName(this.selectedIndustry.industry);
    description.textContent = `${industryName} - ${this.selectedIndustry.description}`;
  }

  private async getRecommendation(): Promise<void> {
    if (!this.currentDataId || !this.selectedIndustry) return;

    try {
      const response = await fetch(`${this.apiURL}/recommend-by-industry`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          data_id: this.currentDataId,
          industry: this.selectedIndustry.industry,
          enable_cross_validation: true
        })
      });

      const recommendation: IndustryRecommendation = await response.json();
      this.showRecommendation(recommendation);

      if (this.onIndustrySelect) {
        this.onIndustrySelect(this.selectedIndustry);
      }
    } catch (error) {
      console.error('获取推荐参数失败:', error);
      alert('获取推荐参数失败，请稍后重试');
    }
  }

  private showRecommendation(recommendation: IndustryRecommendation): void {
    const panel = this.container.querySelector('#recommendation-panel') as HTMLElement;
    const content = this.container.querySelector('.recommendation-content') as HTMLElement;

    content.innerHTML = `
      <div class="recommendation-item">
        <span class="recommendation-label">${I18n.t('industry.recommendation.industry')}:</span>
        <span class="recommendation-value">${recommendation.industry_name}</span>
      </div>
      <div class="recommendation-item">
        <span class="recommendation-label">${I18n.t('industry.recommendation.method')}:</span>
        <span class="recommendation-value">${recommendation.recommended_method}</span>
      </div>
      <div class="recommendation-item">
        <span class="recommendation-label">${I18n.t('industry.recommendation.variogram')}:</span>
        <span class="recommendation-value">${recommendation.recommended_variogram}</span>
      </div>
      <div class="recommendation-item">
        <span class="recommendation-label">${I18n.t('industry.recommendation.resolution')}:</span>
        <span class="recommendation-value">${recommendation.recommended_grid_resolution}</span>
      </div>
      <div class="recommendation-item">
        <span class="recommendation-label">${I18n.t('industry.recommendation.nlags')}:</span>
        <span class="recommendation-value">${recommendation.recommended_nlags}</span>
      </div>
      <div class="recommendation-item">
        <span class="recommendation-label">${I18n.t('industry.recommendation.anisotropy')}:</span>
        <span class="recommendation-value">${recommendation.enable_anisotropy ? I18n.t('industry.recommendation.enabled') : I18n.t('industry.recommendation.disabled')}</span>
      </div>
      <div class="recommendation-item">
        <span class="recommendation-label">${I18n.t('industry.recommendation.trend')}:</span>
        <span class="recommendation-value">${recommendation.enable_trend_detection ? I18n.t('industry.recommendation.enabled') : I18n.t('industry.recommendation.disabled')}</span>
      </div>
      <div class="recommendation-message">${recommendation.message}</div>
    `;

    panel.classList.remove('hidden');
  }

  private showTemplateDialog(industry: IndustryConfig): void {
    const dialog = this.container.querySelector('#template-dialog') as HTMLElement;
    const description = this.container.querySelector('.template-description') as HTMLElement;

    const localizedFilename = I18n.getTemplateFilename(industry.industry);
    const industryName = I18n.getIndustryName(industry.industry);

    description.textContent = I18n.t('template.downloadQuestion', {
      industry: industryName,
      filename: localizedFilename
    });
    dialog.classList.remove('hidden');
  }

  private hideTemplateDialog(): void {
    const dialog = this.container.querySelector('#template-dialog') as HTMLElement;
    dialog.classList.add('hidden');
  }

  private async downloadTemplate(filename: string): Promise<void> {
    try {
      const response = await fetch(`${this.apiURL}/templates/${filename}`);

      if (!response.ok) {
        throw new Error('下载模板失败');
      }

      const blob = await response.blob();
      const arrayBuffer = await blob.arrayBuffer();
      const uint8Array = new Uint8Array(arrayBuffer);

      // 获取本地化的文件名
      const localizedFilename = this.selectedIndustry ? I18n.getTemplateFilename(this.selectedIndustry.industry) : filename;

      // 如果是 Electron 环境，使用保存对话框让用户选择保存位置
      if (window.electronAPI && (window.electronAPI as any).saveFile) {
        const result = await (window.electronAPI as any).saveFile({
          title: I18n.t('template.downloadDialog'),
          defaultPath: localizedFilename,
          filters: [
            { name: 'GeoJSON 文件', extensions: ['geojson', 'json'] },
            { name: '所有文件', extensions: ['*'] }
          ],
          data: uint8Array
        });

        if (result.success && result.filePath) {
          // 显示询问是否跳转到文件位置的弹窗
          TemplateDownloader.showOpenLocationDialog(result.filePath);
        }
      } else {
        // 浏览器环境，使用默认下载方式
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = localizedFilename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        // 显示询问是否跳转到文件位置的弹窗
        TemplateDownloader.showOpenLocationDialog(localizedFilename);
      }
    } catch (error) {
      console.error('下载模板失败:', error);
      alert(I18n.t('template.downloadFailed'));
    }
  }

  /**
   * 设置行业选择回调
   */
  public setIndustrySelectCallback(callback: (industry: IndustryConfig) => void): void {
    this.onIndustrySelect = callback;
  }

  /**
   * 设置模板下载回调
   */
  public setTemplateDownloadCallback(callback: (template: string) => void): void {
    this.onTemplateDownload = callback;
  }

  /**
   * 获取选中的行业配置
   */
  public getSelectedIndustry(): IndustryConfig | null {
    return this.selectedIndustry;
  }

  /**
   * 获取当前数据ID
   */
  public getCurrentDataId(): string {
    return this.currentDataId;
  }

  /**
   * 设置数据ID
   */
  public setDataId(dataId: string): void {
    const input = this.container.querySelector('#data-id') as HTMLInputElement;
    input.value = dataId;
    this.currentDataId = dataId;
    this.updateButtons();
  }

  /**
   * 销毁组件
   */
  public destroy(): void {
    this.container.innerHTML = '';
  }
}