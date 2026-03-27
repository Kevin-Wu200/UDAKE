import { computed } from 'vue';
import { storeToRefs } from 'pinia';
import { useAppStore } from '../stores/app';
import { translate } from './messages';

export function useI18nText() {
  const appStore = useAppStore();
  const { language } = storeToRefs(appStore);

  const t = (key: string) => translate(language.value, key);

  return {
    language: computed(() => language.value),
    t
  };
}
