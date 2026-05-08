import { computed } from 'vue';
import { storeToRefs } from 'pinia';
import { useAppStore } from '../stores/app';
import { translate } from './messages';
import { translate_company } from './company_messages'

export function useI18nText() {
  const appStore = useAppStore();
  const { language } = storeToRefs(appStore);

  const t = (key: string, params?: Record<string, any>) => translate(language.value, key, params);
  const tc = (key: string, params?: Record<string, any>) => translate_company(language.value, key, params);

  return {
    language: computed(() => language.value),
    t,
    tc
  };
}
