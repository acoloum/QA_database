import { describe, expect, it, vi } from 'vitest';

import { createTimerTracker } from './pendingTimers';

const makeScope = () => {
  const scope = {
    setTimeout: ((handler: TimerHandler, timeout?: number, ...args: unknown[]) =>
      globalThis.setTimeout(handler, timeout, ...args)) as typeof setTimeout,
    clearTimeout: ((handle?: ReturnType<typeof setTimeout>) =>
      globalThis.clearTimeout(handle)) as typeof clearTimeout,
  };
  return scope;
};

describe('createTimerTracker', () => {
  it('清掉測試檔結束時仍在排隊的計時器', () => {
    vi.useFakeTimers();
    const scope = makeScope();
    const tracker = createTimerTracker(scope);
    const restore = tracker.install();

    const leaked = vi.fn();
    // 模擬轉場卸載後沒有人取消的補送計時器
    scope.setTimeout(leaked, 5);
    expect(tracker.pendingCount()).toBe(1);

    tracker.clearPending();
    vi.advanceTimersByTime(50);

    expect(leaked).not.toHaveBeenCalled();
    expect(tracker.pendingCount()).toBe(0);
    restore();
    vi.useRealTimers();
  });

  it('正常觸發的計時器行為不變，且不再被視為排隊中', () => {
    vi.useFakeTimers();
    const scope = makeScope();
    const tracker = createTimerTracker(scope);
    const restore = tracker.install();

    const handler = vi.fn();
    scope.setTimeout(handler, 10, 'a', 1);
    vi.advanceTimersByTime(10);

    expect(handler).toHaveBeenCalledWith('a', 1);
    expect(tracker.pendingCount()).toBe(0);
    restore();
    vi.useRealTimers();
  });

  it('還原後 setTimeout 回到原本的實作', () => {
    const scope = makeScope();
    const before = scope.setTimeout;
    const restore = createTimerTracker(scope).install();
    expect(scope.setTimeout).not.toBe(before);
    restore();
    expect(scope.setTimeout).toBe(before);
  });
});
