/**
 * 追蹤測試期間排定、結束時仍未觸發的計時器。
 *
 * react-bootstrap 的轉場（Modal/Fade/Collapse）透過 dom-helpers 的 transitionEnd
 * 排一個 setTimeout，在 CSS transition 時間後手動補送 transitionend。元件在計時器
 * 到期前卸載時沒有人取消它——react-transition-group 的 addEndListener 沒有提供
 * 取消管道。這個孤兒計時器若在測試檔結束、jsdom 環境拆除之後才觸發，dom-helpers
 * 取用的是「全域」document 而非 node.ownerDocument，於是丟出
 * ReferenceError: document is not defined，讓整個 vitest run 以失敗收場，即使每一
 * 支測試都通過（CI 曾因此紅過：142 檔 779 測試全過，卻 exit 1）。
 *
 * 對策是在每個測試檔跑完時把仍在排隊的計時器清掉——測試都結束了，還沒燒完的
 * 計時器依定義就是洩漏，不該再有副作用。
 */

export interface TimerScope {
  setTimeout: typeof setTimeout;
  clearTimeout: typeof clearTimeout;
}

export interface TimerTracker {
  /** 掛上包裝後的 setTimeout；回傳還原用的函式。 */
  install(): () => void;
  /** 清掉所有仍在排隊的計時器。 */
  clearPending(): void;
  /** 目前仍在排隊的計時器數量（供測試斷言）。 */
  pendingCount(): number;
}

export const createTimerTracker = (scope: TimerScope): TimerTracker => {
  const pending = new Set<ReturnType<typeof setTimeout>>();
  const original = scope.setTimeout;

  const install = () => {
    const wrapped = ((handler: TimerHandler, timeout?: number, ...args: unknown[]) => {
      const handle = original(
        (...called: unknown[]) => {
          pending.delete(handle);
          if (typeof handler === 'function') {
            (handler as (...rest: unknown[]) => void)(...called);
          }
        },
        timeout,
        ...args,
      );
      pending.add(handle);
      return handle;
    }) as typeof setTimeout;

    scope.setTimeout = wrapped;
    return () => {
      scope.setTimeout = original;
    };
  };

  return {
    install,
    clearPending: () => {
      pending.forEach((handle) => scope.clearTimeout(handle));
      pending.clear();
    },
    pendingCount: () => pending.size,
  };
};
