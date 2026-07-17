import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import PatrolOutlierManagerModal from './PatrolOutlierManagerModal';
import * as usePatrolHooks from '../../hooks/usePatrol';

vi.mock('../../hooks/usePatrol', async () => {
    const actual = await vi.importActual('../../hooks/usePatrol');
    return { ...actual, usePatrolDetails: vi.fn(), useSetPatrolDetailExclusion: vi.fn() };
});

const renderWithClient = (ui: React.ReactElement) => {
    const client = new QueryClient();
    return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
};

describe('PatrolOutlierManagerModal', () => {
    const mutate = vi.fn();

    beforeEach(() => {
        mutate.mockClear();
        vi.mocked(usePatrolHooks.usePatrolDetails).mockReturnValue({
            data: [{
                識別碼: 1, 組別: 1, 測量項目: '外徑', 測量位置: '前段',
                最小值: 9.8, 最大值: 10.2, 排除統計: false, 排除原因: null,
            }],
            isLoading: false,
        } as never);
        vi.mocked(usePatrolHooks.useSetPatrolDetailExclusion).mockReturnValue({
            mutate, isPending: false,
        } as never);
    });

    it('顯示量測明細列表', () => {
        renderWithClient(<PatrolOutlierManagerModal mainId={123} show onHide={() => {}} />);
        expect(screen.getByText('外徑')).toBeInTheDocument();
        expect(screen.getByText('9.8 / 10.2')).toBeInTheDocument();
        expect(screen.getByText('計入統計')).toBeInTheDocument();
    });

    it('未填原因時無法標示離群', () => {
        renderWithClient(<PatrolOutlierManagerModal mainId={123} show onHide={() => {}} />);
        const btn = screen.getByRole('button', { name: '標示離群' });
        expect(btn).toBeDisabled();
    });

    it('填寫原因後可標示離群', async () => {
        renderWithClient(<PatrolOutlierManagerModal mainId={123} show onHide={() => {}} />);
        const input = screen.getByPlaceholderText('離群原因（必填）');
        fireEvent.change(input, { target: { value: '量測儀器故障' } });
        const btn = screen.getByRole('button', { name: '標示離群' });
        await waitFor(() => expect(btn).not.toBeDisabled());
        fireEvent.click(btn);
        expect(mutate).toHaveBeenCalledWith(
            { id: 1, excluded: true, reason: '量測儀器故障' },
            expect.anything(),
        );
    });
});
