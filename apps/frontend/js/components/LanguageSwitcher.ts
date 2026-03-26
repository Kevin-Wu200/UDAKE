/**
 * 语言切换组件
 * 提供语言切换功能
 */

import { I18n } from '../utils/I18n';

interface LanguageOption {
  code: string;
  name: string;
  flag: string;
}

const languages: LanguageOption[] = [
  { code: 'zh-CN', name: '简体中文', flag: '🇨🇳' },
  { code: 'en-US', name: 'English', flag: '🇺🇸' }
];

export class LanguageSwitcher {
  private currentLanguage: string;
  private container: HTMLElement;
  private onLanguageChange?: (lang: string) => void;

  constructor(container: HTMLElement, onLanguageChange?: (lang: string) => void) {
    this.container = container;
    this.currentLanguage = localStorage.getItem('udake_locale') || I18n.locale || 'zh-CN';
    this.onLanguageChange = onLanguageChange;
    this.render();
  }

  render(): void {
    this.container.innerHTML = `
      <div class="language-switcher">
        <button class="language-button">
          ${this.getCurrentLanguage().flag} ${this.getCurrentLanguage().name}
          <span class="arrow">▼</span>
        </button>
        <div class="language-dropdown">
          ${languages.map(lang => `
            <div class="language-option" data-lang="${lang.code}">
              ${lang.flag} ${lang.name}
            </div>
          `).join('')}
        </div>
      </div>
    `;

    this.bindEvents();
  }

  private getCurrentLanguage(): LanguageOption {
    return languages.find(lang => lang.code === this.currentLanguage) || languages[0];
  }

  private bindEvents(): void {
    const button = this.container.querySelector('.language-button') as HTMLElement;
    const dropdown = this.container.querySelector('.language-dropdown') as HTMLElement;
    const options = this.container.querySelectorAll('.language-option');

    button.addEventListener('click', (e) => {
      e.stopPropagation();
      dropdown.classList.toggle('show');
    });

    options.forEach(option => {
      option.addEventListener('click', (e) => {
        const langCode = (e.currentTarget as HTMLElement).dataset.lang;
        if (langCode) {
          this.changeLanguage(langCode);
          dropdown.classList.remove('show');
        }
      });
    });

    document.addEventListener('click', () => {
      dropdown.classList.remove('show');
    });
  }

  private changeLanguage(langCode: string): void {
    this.currentLanguage = langCode;

    // 更新统一 I18n 管理器
    I18n.setLocale(langCode);

    // 更新 UI
    this.render();

    // 触发回调
    if (this.onLanguageChange) {
      this.onLanguageChange(langCode);
    }

    // 保存到 localStorage
    localStorage.setItem('udake_locale', langCode);
  }
}

// 导出 CSS 样式
export const languageSwitcherStyles = `
  .language-switcher {
    position: relative;
    display: inline-block;
  }

  .language-button {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    background: white;
    border: 1px solid #ddd;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
    transition: all 0.2s;
  }

  .language-button:hover {
    background: #f5f5f5;
  }

  .language-button .arrow {
    font-size: 10px;
    transition: transform 0.2s;
  }

  .language-dropdown {
    position: absolute;
    top: 100%;
    right: 0;
    margin-top: 4px;
    background: white;
    border: 1px solid #ddd;
    border-radius: 4px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    display: none;
    min-width: 150px;
    z-index: 1000;
  }

  .language-dropdown.show {
    display: block;
  }

  .language-option {
    padding: 10px 16px;
    cursor: pointer;
    transition: background 0.2s;
  }

  .language-option:hover {
    background: #f5f5f5;
  }
`;
