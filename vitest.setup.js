// Vitest setup file
// Mock global browser APIs not implemented in jsdom

global.alert = vi.fn();
global.confirm = vi.fn(() => true);
global.prompt = vi.fn(() => '');