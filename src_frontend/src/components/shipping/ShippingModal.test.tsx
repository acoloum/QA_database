import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ShippingModal from './ShippingModal';
import type { ToleranceResult } from '../../types';

type Deferred<T> = {
  promise: Promise<T>;
  resolve: (value: T) => void;
};

const deferred = <T,>(): Deferred<T> => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(res => {
    resolve = res;
  });
  return { promise, resolve };
};

const checkToleranceMutate = vi.fn();

vi.mock('react-hot-toast', () => ({
  default: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock('../../hooks/useShipping', () => ({
  useInspectors: () => ({ data: [{ id: 1, name: '檢驗員A' }] }),
  useVendors: () => ({ data: [{ id: 10, name: '廠商A' }] }),
  useShippingDetail: () => ({ data: null, isLoading: false }),
  useCreateShipping: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateShipping: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useCheckTolerance: () => ({ mutateAsync: checkToleranceMutate }),
}));

const toleranceResponse = (specLabel: string): ToleranceResult => ({
  success: true,
  found: true,
  is_valid: true,
  violates: [],
  message: specLabel,
  tolerances: [{
    項目: '外徑',
    標準值: null,
    公差上限: null,
    公差下限: null,
    尺寸上限: 10,
    尺寸下限: 1,
    單位: 'mm',
  }],
});

describe('ShippingModal', () => {
  beforeEach(() => {
    checkToleranceMutate.mockReset();
  });

  it('ignores stale tolerance lookup results after form keys change', async () => {
    const stale = deferred<ToleranceResult>();
    const current = deferred<ToleranceResult>();
    checkToleranceMutate
      .mockReturnValueOnce(stale.promise)
      .mockReturnValueOnce(current.promise);

    render(
      <ShippingModal
        show
        editId={null}
        handleClose={() => undefined}
        onSuccess={() => undefined}
      />,
    );

    const selects = screen.getAllByRole('combobox');
    const textInputs = screen.getAllByRole('textbox');
    const vendorSelect = selects[1];
    const specInput = textInputs[0];
    const materialInput = textInputs[1];

    fireEvent.change(vendorSelect, { target: { value: '廠商A' } });
    fireEvent.change(materialInput, { target: { value: 'A6061' } });
    fireEvent.change(specInput, { target: { value: 'SPEC-OLD' } });

    await waitFor(() => expect(checkToleranceMutate).toHaveBeenCalledTimes(1));

    fireEvent.change(specInput, { target: { value: 'SPEC-NEW' } });
    await waitFor(() => expect(checkToleranceMutate).toHaveBeenCalledTimes(2));

    await act(async () => {
      stale.resolve(toleranceResponse('old'));
    });
    expect(screen.queryByText(/公差標準已載入/)).not.toBeInTheDocument();

    await act(async () => {
      current.resolve(toleranceResponse('new'));
    });
    await waitFor(() => expect(screen.getByText(/公差標準已載入/)).toBeInTheDocument());
  });
});
