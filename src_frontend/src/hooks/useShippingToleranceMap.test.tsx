import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';

import api from '../services/api';
import type { ShippingInspection } from '../types';
import {
  resolveToleranceStandardValue,
  toToleranceLimits,
  useShippingToleranceMap,
} from './useShippingToleranceMap';

vi.mock('../services/api', () => ({
  default: {
    get: vi.fn(),
  },
}));

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    {children}
  </QueryClientProvider>
);

describe('useShippingToleranceMap', () => {
  it('resolves tolerance standard values from parsed spec before configured fallback', () => {
    expect(resolveToleranceStandardValue(12, 8)).toBe(12);
    expect(resolveToleranceStandardValue(undefined, 10)).toBe(10);
    expect(resolveToleranceStandardValue(0, 8)).toBe(8);
    expect(resolveToleranceStandardValue(0, 0)).toBeNull();
    expect(resolveToleranceStandardValue(undefined, null)).toBeNull();
  });

  it('builds tolerance limits with configured standard fallback when spec has no usable nominal', () => {
    const limits = toToleranceLimits(
      {
        success: true,
        found: true,
        tolerances: [{
          項目: '外徑',
          標準值: 10,
          公差上限: 0.2,
          公差下限: -0.1,
          尺寸上限: null,
          尺寸下限: null,
          單位: 'mm',
        }],
      },
      '',
    );

    expect(limits?.外徑).toEqual({ lsl: 9.9, usl: 10.2 });
  });

  it('skips relative tolerances when neither spec nor configured standard has a usable nominal', () => {
    const limits = toToleranceLimits(
      {
        success: true,
        found: true,
        tolerances: [{
          項目: '外徑',
          標準值: 0,
          公差上限: 0.2,
          公差下限: -0.1,
          尺寸上限: null,
          尺寸下限: null,
          單位: 'mm',
        }],
      },
      '',
    );

    expect(limits).toEqual({});
  });

  it('deduplicates tolerance checks by material/spec/vendor combo', async () => {
    const inspections: ShippingInspection[] = [
      {
        id: 1,
        date: '2026-06-01',
        material: '6061',
        spec: '10*2',
        vendor_name: '廠商A',
        group_count: 1,
        is_ng: false,
        measurements: {},
      },
      {
        id: 2,
        date: '2026-06-02',
        material: '6061',
        spec: '10*2',
        vendor_name: '廠商A',
        group_count: 1,
        is_ng: false,
        measurements: {},
      },
    ];

    vi.mocked(api.get).mockImplementation((url: string) => {
      if (url === '/vendors') {
        return Promise.resolve({ data: [{ id: 7, name: '廠商A' }] });
      }
      if (url.startsWith('/tolerance/check?')) {
        return Promise.resolve({
          data: {
            success: true,
            found: true,
            tolerances: [{
              項目: '外徑',
              標準值: null,
              公差上限: null,
              公差下限: null,
              尺寸上限: 10.2,
              尺寸下限: 9.8,
              單位: 'mm',
            }],
          },
        });
      }
      return Promise.reject(new Error(`unexpected url: ${url}`));
    });

    const { result } = renderHook(() => useShippingToleranceMap(inspections), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const toleranceCalls = vi.mocked(api.get).mock.calls.filter(([url]) => String(url).startsWith('/tolerance/check?'));
    expect(toleranceCalls).toHaveLength(1);
    expect(result.current.data?.['6061|||10*2|||廠商A']?.外徑).toEqual({ lsl: 9.8, usl: 10.2 });
  });
});
