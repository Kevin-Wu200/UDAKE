// Vitest setup file
// Mock global browser APIs not implemented in jsdom

global.alert = vi.fn();
global.confirm = vi.fn(() => true);
global.prompt = vi.fn(() => '');

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
const mockDB = {
  objectStores: {},
  transaction: (storeName, mode) => ({
    objectStore: (name) => {
      if (!mockDB.objectStores[name]) {
        mockDB.objectStores[name] = {};
      }
      return {
        get: (key) => {
          const request = { onsuccess: null, onerror: null };
          setTimeout(() => {
            if (request.onsuccess) {
              request.onsuccess({ target: { result: mockDB.objectStores[name][key] || undefined } });
            }
          }, 0);
          return request;
        },
        put: (data) => {
          const request = { onsuccess: null, onerror: null };
          setTimeout(() => {
            if (request.onsuccess) {
              mockDB.objectStores[name][data.id || data.taskId] = data;
              request.onsuccess({ target: { result: data } });
            }
          }, 0);
          return request;
        },
        delete: (key) => {
          const request = { onsuccess: null, onerror: null };
          setTimeout(() => {
            delete mockDB.objectStores[name][key];
            if (request.onsuccess) request.onsuccess({ target: { result: undefined } });
          }, 0);
          return request;
        },
        getAll: () => {
          const request = { onsuccess: null, onerror: null };
          setTimeout(() => {
            if (request.onsuccess) {
              request.onsuccess({ target: { result: Object.values(mockDB.objectStores[name] || {}) } });
            }
          }, 0);
          return request;
        },
        clear: () => {
          const request = { onsuccess: null, onerror: null };
          setTimeout(() => {
            mockDB.objectStores[name] = {};
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
                request.onsuccess({ target: { result: Object.values(mockDB.objectStores[name] || {}) } });
              }
            }, 0);
            return request;
          }
        })
      };
    }
  })
};

global.indexedDB = {
  open: (name, version) => {
    const request = {
      onupgradeneeded: null,
      onsuccess: null,
      onerror: null,
      result: mockDB,
      error: null
    };
    // 触发 onsuccess
    setTimeout(() => {
      if (request.onsuccess) request.onsuccess({ target: request });
    }, 0);
    return request;
  }
};