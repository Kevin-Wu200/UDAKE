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

const languageFlags: Record<string, string> = {
  'zh-CN': '🇨🇳',
  'en-US': '🇺🇸',
  'zh-TW': '🇹🇼',
  'ja-JP': '🇯🇵',
  'ko-KR': '🇰🇷'
};

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

  private getLanguageOptions(): LanguageOption[] {
    return I18n.getAvailableLocales().map((locale) => ({
      code: locale.code,
      name: locale.name,
      flag: languageFlags[locale.code] || '🌐'
    }));
  }

  render(): void {
    const languages = this.getLanguageOptions();
    const current = this.getCurrentLanguage();

    this.container.innerHTML = `
      <div class="language-switcher">
        <button class="language-button" type="button">
          <span class="language-current">${current.flag} ${current.name}</span>
          <span class="arrow">▼</span>
        </button>
        <div class="language-dropdown">
          ${languages.map(lang => `
            <button class="language-option ${lang.code === current.code ? 'active' : ''}" type="button" data-lang="${lang.code}">
              ${lang.flag} ${lang.name}
            </button>
          `).join('')}
        </div>
      </div>
    `;

    this.bindEvents();
  }

  private getCurrentLanguage(): LanguageOption {
    const languages = this.getLanguageOptions();
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

    options.forEach((option) => {
      option.addEventListener('click', (e) => {
        const langCode = (e.currentTarget as HTMLElement).dataset.lang;
        if (langCode) {
          void this.changeLanguage(langCode);
          dropdown.classList.remove('show');
        }
      });
    });

    document.addEventListener('click', () => {
      dropdown.classList.remove('show');
    });
  }

  private async changeLanguage(langCode: string): Promise<void> {
    const changed = await I18n.setLocaleAsync(langCode);
    if (!changed) {
      return;
    }

    this.currentLanguage = I18n.locale;
    this.render();

    if (this.onLanguageChange) {
      this.onLanguageChange(this.currentLanguage);
    }
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
    border-radius: 10px;
    cursor: pointer;
    font-size: 14px;
    transition: all 0.2s;
  }

  .language-current {
    white-space: nowrap;
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
    min-width: 180px;
    z-index: 1000;
    animation: language-dropdown-fade 0.18s ease;
  }

  .language-dropdown.show {
    display: block;
  }

  .language-option {
    width: 100%;
    text-align: left;
    padding: 10px 16px;
    cursor: pointer;
    transition: background 0.2s;
    border: 0;
    background: transparent;
  }

  .language-option:hover {
    background: #f5f5f5;
  }

  .language-option.active {
    background: #ecf5ff;
    color: #1f73b7;
    font-weight: 600;
  }

  @keyframes language-dropdown-fade {
    from {
      opacity: 0;
      transform: translateY(-4px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
`;
