/**
 * Test setup and global mocks
 */

// Mock fetch globally
global.fetch = jest.fn();

// Mock AbortSignal.timeout for older Node versions
if (!AbortSignal.timeout) {
  AbortSignal.timeout = (ms: number) => {
    const controller = new AbortController();
    setTimeout(() => controller.abort(), ms);
    return controller.signal;
  };
}

beforeEach(() => {
  jest.clearAllMocks();
});