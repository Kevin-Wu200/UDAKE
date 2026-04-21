import { defineStore } from 'pinia';

export type AppLanguage = 'zh-CN' | 'en-US' | 'ja-JP' | 'zh-TW' | 'ko-KR';

const LANGUAGE_KEY = 'admin_language';

export const useAppStore = defineStore('app', {
  state: () => ({
    language: (localStorage.getItem(LANGUAGE_KEY) as AppLanguage) || 'zh-CN'
  }),
  actions: {
    setLanguage(language: AppLanguage) {
      this.language = language;
      localStorage.setItem(LANGUAGE_KEY, language);
    }
  }
});
