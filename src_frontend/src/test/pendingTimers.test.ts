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

  it('取消的計時器會離開排隊集合，不虛報也不無限成長', () => {
    vi.useFakeTimers();
    const scope = makeScope();
    const tracker = createTimerTracker(scope);
    const restore = tracker.install();

    const handle = scope.setTimeout(() => {}, 5);
    expect(tracker.pendingCount()).toBe(1);
    scope.clearTimeout(handle);
    expect(tracker.pendingCount()).toBe(0);

    restore();
    vi.useRealTimers();
  });

  it('即使測試留著假計時器沒還原，clearPending 仍以原始 clearTimeout 取消', () => {
    const scope = makeScope();
    const tracker = createTimerTracker(scope);
    const restore = tracker.install();

    scope.setTimeout(() => {}, 5);
    // 模擬測試裝了假計時器卻沒還原：scope 上的 clearTimeout 被換掉
    const fakeClear = vi.fn();
    scope.clearTimeout = fakeClear as unknown as typeof clearTimeout;

    tracker.clearPending();

    expect(fakeClear).not.toHaveBeenCalled();
    expect(tracker.pendingCount()).toBe(0);
    restore();
  });

  it('還原後 setTimeout 與 clearTimeout 都回到原本的實作', () => {
    const scope = makeScope();
    const beforeSet = scope.setTimeout;
    const beforeClear = scope.clearTimeout;
    const restore = createTimerTracker(scope).install();
    expect(scope.setTimeout).not.toBe(beforeSet);
    expect(scope.clearTimeout).not.toBe(beforeClear);
    restore();
    expect(scope.setTimeout).toBe(beforeSet);
    expect(scope.clearTimeout).toBe(beforeClear);
  });
});
