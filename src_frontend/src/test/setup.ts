import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterAll, afterEach } from 'vitest';

import { createTimerTracker } from './pendingTimers';

// 見 pendingTimers.ts：轉場元件卸載後留下的孤兒計時器若在 jsdom 拆除後才觸發，
// 會讓整個 run 失敗，即使測試全過。
const timers = createTimerTracker(globalThis as unknown as {
  setTimeout: typeof setTimeout;
  clearTimeout: typeof clearTimeout;
});
const restoreTimers = timers.install();

afterEach(() => {
  cleanup();
});

afterAll(() => {
  timers.clearPending();
  restoreTimers();
});
