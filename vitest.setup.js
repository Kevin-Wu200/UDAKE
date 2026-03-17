// Vitest setup file
// Mock global browser APIs not implemented in jsdom

// 抑制测试中 errorHandler 产生的 Unhandled Rejection
process.on('unhandledRejection', () => {});

global.alert = vi.fn();
global.confirm = vi.fn(() => true);
global.prompt = vi.fn(() => '');

// 全局 fetch mock（兜底，防止真实网络请求泄漏）
if (!global.fetch || !global.fetch._isMockFunction) {
  global.fetch = vi.fn(() =>
    Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve({}),
      text: () => Promise.resolve(''),
      headers: new Headers(),
    })
  );
}

// 每次测试前清理状态
beforeEach(() => {
  try { localStorage.clear(); } catch { /* ignore */ }
});

// Mock localStorage
const localStorageMock = (() => {
  let store = {};
  return {
    getItem: (key) => store[key] || null,
    setItem: (key, value) => { store[key] = value.toString(); },
    removeItem: (key) => { delete store[key]; },
    clear: () => { store = {}; },
    get length() { return Object.keys(store).length; },
    key: (index) => { return Object.keys(store)[index] || null; }
  };
})();
global.localStorage = localStorageMock;

// Mock IndexedDB
function createMockDB() {
  const stores = {};
  const storeNames = [];

  const objectStoreNames = {
    contains: (name) => storeNames.includes(name),
    get length() { return storeNames.length; },
  };

  const db = {
    objectStoreNames,
    createObjectStore: (name, options) => {
      if (!storeNames.includes(name)) storeNames.push(name);
      stores[name] = {};
      return createObjectStoreMock(stores, name);
    },
    transaction: (storeName, mode) => ({
      objectStore: (name) => {
        if (!stores[name]) stores[name] = {};
        return createObjectStoreMock(stores, name);
      },
    }),
    close: () => {},
  };

  return db;
}

function createObjectStoreMock(stores, name) {
  return {
    get: (key) => {
      const request = { onsuccess: null, onerror: null };
      setTimeout(() => {
        if (request.onsuccess) {
          request.onsuccess({ target: { result: stores[name][key] || undefined } });
        }
      }, 0);
      return request;
    },
    put: (data) => {
      const request = { onsuccess: null, onerror: null };
      setTimeout(() => {
        const key = data.id || data.taskId;
        if (key !== undefined) stores[name][key] = data;
        if (request.onsuccess) request.onsuccess({ target: { result: data } });
      }, 0);
      return request;
    },
    delete: (key) => {
      const request = { onsuccess: null, onerror: null };
      setTimeout(() => {
        delete stores[name][key];
        if (request.onsuccess) request.onsuccess({ target: { result: undefined } });
      }, 0);
      return request;
    },
    getAll: () => {
      const request = { onsuccess: null, onerror: null };
      setTimeout(() => {
        if (request.onsuccess) {
          request.onsuccess({ target: { result: Object.values(stores[name] || {}) } });
        }
      }, 0);
      return request;
    },
    clear: () => {
      const request = { onsuccess: null, onerror: null };
      setTimeout(() => {
        stores[name] = {};
        if (request.onsuccess) request.onsuccess({ target: { result: undefined } });
      }, 0);
      return request;
    },
    createIndex: () => {},
    index: () => ({
      getAll: () => {
        const request = { onsuccess: null, onerror: null };
        setTimeout(() => {
          if (request.onsuccess) {
            request.onsuccess({ target: { result: Object.values(stores[name] || {}) } });
          }
        }, 0);
        return request;
      },
    }),
  };
}

global.indexedDB = {
  open: (name, version) => {
    const mockDB = createMockDB();
    const request = {
      onupgradeneeded: null,
      onsuccess: null,
      onerror: null,
      result: mockDB,
      error: null,
    };
    // 先触发 onupgradeneeded，再触发 onsuccess
    setTimeout(() => {
      if (request.onupgradeneeded) {
        request.onupgradeneeded({ target: { result: mockDB } });
      }
      if (request.onsuccess) {
        request.onsuccess({ target: request });
      }
    }, 0);
    return request;
  },
  deleteDatabase: (name) => {
    const request = { onsuccess: null, onerror: null };
    setTimeout(() => {
      if (request.onsuccess) request.onsuccess({ target: { result: undefined } });
    }, 0);
    return request;
  },
};
