import { computed } from 'vue';
import { storeToRefs } from 'pinia';
import { useAppStore } from '../stores/app';
import { translate } from './messages';
import { translate_user } from './user_messages';

export function useI18nText() {
  const appStore = useAppStore();
  const { language } = storeToRefs(appStore);

  const t = (key: string) => translate(language.value, key);

  return {
    language: computed(() => language.value),
    t
  };
}


export function useI18nText_user() {
  const appStore = useAppStore();
  return {
    t: (key: string, params?: Record<string, string | number>) => 
      translate_user(appStore.language, key, params)
  };
}