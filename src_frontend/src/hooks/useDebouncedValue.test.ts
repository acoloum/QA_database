import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useDebouncedValue } from './useDebouncedValue';

describe('useDebouncedValue', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('初次回傳即為當前值', () => {
    const { result } = renderHook(() => useDebouncedValue('6061', 300));
    expect(result.current).toBe('6061');
  });

  it('值變動後要過了 delay 才更新', () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebouncedValue(value, 300),
      { initialProps: { value: '6' } },
    );

    rerender({ value: '60' });
    rerender({ value: '606' });
    rerender({ value: '6061' });

    // 尚未到 delay，仍是初始值
    expect(result.current).toBe('6');

    act(() => {
      vi.advanceTimersByTime(299);
    });
    expect(result.current).toBe('6');

    // 最後一次變動起算滿 300ms 後，只跳到最終值（中間值被略過）
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(result.current).toBe('6061');
  });

  it('連續變動時每次都重置計時，避免中間值外洩', () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebouncedValue(value, 300),
      { initialProps: { value: 'a' } },
    );

    rerender({ value: 'ab' });
    act(() => {
      vi.advanceTimersByTime(200);
    });
    // 200ms 時又輸入一個字，計時應重置
    rerender({ value: 'abc' });
    act(() => {
      vi.advanceTimersByTime(200);
    });
    // 距離最後一次變動只過了 200ms，尚未更新
    expect(result.current).toBe('a');

    act(() => {
      vi.advanceTimersByTime(100);
    });
    expect(result.current).toBe('abc');
  });
});
