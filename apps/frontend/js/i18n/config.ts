import zhTWMessages from '../locales/zh-TW.json';
import jaJPMessages from '../locales/ja-JP.json';
import koKRMessages from '../locales/ko-KR.json';

export type LocaleMessages = Record<string, string>;
export type LocaleLoader = () => Promise<LocaleMessages>;

export const I18N_DEFAULT_LOCALE = 'zh-CN';
export const I18N_FALLBACK_LOCALE = 'en-US';
export const I18N_AVAILABLE_LOCALE_CODES = ['zh-CN', 'en-US', 'zh-TW', 'ja-JP', 'ko-KR'] as const;
export const I18N_RTL_LOCALE_PREFIXES = ['ar', 'fa', 'he', 'ur'] as const;

export const I18N_LAZY_LOCALE_LOADERS: Record<string, LocaleLoader> = {
    'zh-TW': async () => zhTWMessages as LocaleMessages,
    'ja-JP': async () => jaJPMessages as LocaleMessages,
    'ko-KR': async () => koKRMessages as LocaleMessages
};
