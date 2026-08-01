import { renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import api from '../../services/api';
import { useReworkActions } from './useReworkActions';
import toast from 'react-hot-toast';

vi.mock('../../services/api', () => ({
  default: {
    delete: vi.fn(),
    get: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock('react-hot-toast', () => ({
  default: {
    error: vi.fn(),
    success: vi.fn(),
  },
}));

describe('useReworkActions', () => {
  it('刪除重工成本後重新載入明細與列表', async () => {
    vi.mocked(api.delete).mockResolvedValueOnce({ data: {} });
    const reloadDetailData = vi.fn().mockResolvedValue(undefined);
    const loadData = vi.fn().mockResolvedValue(undefined);

    const { result } = renderHook(() => useReworkActions({
      applications: [],
      selectedReworkDetail: null,
      reloadDetailData,
      loadData,
      setFollowUpModal: vi.fn(),
      hasPermission: () => true,
    }));

    await result.current.deleteCost(7);

    expect(api.delete).toHaveBeenCalledWith('/rework/cost/7');
    expect(reloadDetailData).toHaveBeenCalledTimes(1);
    expect(loadData).toHaveBeenCalledTimes(1);
  });

  it('缺少刪除權限時不呼叫 API 並顯示權限理由', async () => {
    const { result } = renderHook(() => useReworkActions({
      applications: [],
      selectedReworkDetail: null,
      reloadDetailData: vi.fn(),
      loadData: vi.fn(),
      setFollowUpModal: vi.fn(),
      hasPermission: () => false,
    }));

    await result.current.deleteRework(9);

    expect(api.post).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledWith('需要 rework.delete 權限');
  });
});
