import { defineStore } from 'pinia';

const HISTORY_CACHE_KEY = 'admin_history_analysis_cache';
const HISTORY_CACHE_TTL_MS = 15 * 60 * 1000;

export const HISTORY_SECTIONS = [
  'snapshots',
  'compare',
  'trend',
  'anomaly',
  'forecast',
  'reports'
] as const;

export type HistorySection = (typeof HISTORY_SECTIONS)[number];

export interface HistoryPageState {
  datasetId: string;
  versionA: string;
  versionB: string;
}

interface HistoryCacheEntry {
  payload: Record<string, unknown>;
  updatedAt: number;
}

interface HistoryStoreState {
  pageState: Record<HistorySection, HistoryPageState>;
  cache: Record<HistorySection, HistoryCacheEntry>;
}

const createDefaultPageState = (): Record<HistorySection, HistoryPageState> => ({
  snapshots: { datasetId: '', versionA: '', versionB: '' },
  compare: { datasetId: '', versionA: '', versionB: '' },
  trend: { datasetId: '', versionA: '', versionB: '' },
  anomaly: { datasetId: '', versionA: '', versionB: '' },
  forecast: { datasetId: '', versionA: '', versionB: '' },
  reports: { datasetId: '', versionA: '', versionB: '' }
});

const isValidDatasetId = (value: string): boolean => /^[a-zA-Z0-9_-]{0,64}$/.test(value);
const isValidVersion = (value: string): boolean => /^\d{0,6}$/.test(value);

function parseState(raw: string | null): HistoryStoreState | null {
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw) as Partial<HistoryStoreState>;
    const pageState = createDefaultPageState();
    const cache: Record<HistorySection, HistoryCacheEntry> = {
      snapshots: { payload: {}, updatedAt: 0 },
      compare: { payload: {}, updatedAt: 0 },
      trend: { payload: {}, updatedAt: 0 },
      anomaly: { payload: {}, updatedAt: 0 },
      forecast: { payload: {}, updatedAt: 0 },
      reports: { payload: {}, updatedAt: 0 }
    };

    for (const section of HISTORY_SECTIONS) {
      const sectionState = parsed.pageState?.[section];
      pageState[section] = {
        datasetId: typeof sectionState?.datasetId === 'string' && isValidDatasetId(sectionState.datasetId)
          ? sectionState.datasetId
          : '',
        versionA: typeof sectionState?.versionA === 'string' && isValidVersion(sectionState.versionA)
          ? sectionState.versionA
          : '',
        versionB: typeof sectionState?.versionB === 'string' && isValidVersion(sectionState.versionB)
          ? sectionState.versionB
          : ''
      };

      const entry = parsed.cache?.[section];
      if (entry && typeof entry.updatedAt === 'number' && entry.updatedAt > 0 && entry.payload) {
        cache[section] = {
          payload: entry.payload,
          updatedAt: entry.updatedAt
        };
      }
    }

    return { pageState, cache };
  } catch {
    return null;
  }
}

export const useHistoryAnalysisStore = defineStore('history-analysis', {
  state: (): HistoryStoreState => {
    const restored = parseState(localStorage.getItem(HISTORY_CACHE_KEY));
    return (
      restored || {
        pageState: createDefaultPageState(),
        cache: {
          snapshots: { payload: {}, updatedAt: 0 },
          compare: { payload: {}, updatedAt: 0 },
          trend: { payload: {}, updatedAt: 0 },
          anomaly: { payload: {}, updatedAt: 0 },
          forecast: { payload: {}, updatedAt: 0 },
          reports: { payload: {}, updatedAt: 0 }
        }
      }
    );
  },
  actions: {
    patchPageState(section: HistorySection, patch: Partial<HistoryPageState>) {
      const current = this.pageState[section];
      this.pageState[section] = {
        datasetId:
          typeof patch.datasetId === 'string' && isValidDatasetId(patch.datasetId)
            ? patch.datasetId
            : current.datasetId,
        versionA:
          typeof patch.versionA === 'string' && isValidVersion(patch.versionA)
            ? patch.versionA
            : current.versionA,
        versionB:
          typeof patch.versionB === 'string' && isValidVersion(patch.versionB)
            ? patch.versionB
            : current.versionB
      };
      this.persist();
    },
    setCache(section: HistorySection, payload: Record<string, unknown>) {
      this.cache[section] = {
        payload,
        updatedAt: Date.now()
      };
      this.persist();
    },
    getCache(section: HistorySection) {
      const cache = this.cache[section];
      if (!cache.updatedAt) {
        return null;
      }
      if (Date.now() - cache.updatedAt > HISTORY_CACHE_TTL_MS) {
        this.cache[section] = { payload: {}, updatedAt: 0 };
        this.persist();
        return null;
      }
      return cache;
    },
    clearCache(section?: HistorySection) {
      if (section) {
        this.cache[section] = { payload: {}, updatedAt: 0 };
      } else {
        for (const key of HISTORY_SECTIONS) {
          this.cache[key] = { payload: {}, updatedAt: 0 };
        }
      }
      this.persist();
    },
    persist() {
      const payload: HistoryStoreState = {
        pageState: this.pageState,
        cache: this.cache
      };
      localStorage.setItem(HISTORY_CACHE_KEY, JSON.stringify(payload));
    }
  }
});
