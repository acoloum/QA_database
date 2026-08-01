import { useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../../services/api';
import type { ReworkApplication, ReworkStatistics } from '../../types';
import { buildReworkListQuery } from './reworkPageUtils';

interface UseReworkPageDataParams {
  statusFilter: string;
  startDate: string;
  endDate: string;
}

export const useReworkPageData = ({ statusFilter, startDate, endDate }: UseReworkPageDataParams) => {
  const queryClient = useQueryClient();

  // 列表與統計改用 useQuery 註冊快取；篩選條件變更時由 query key 驅動重新載入
  const listQuery = useQuery({
    queryKey: ['rework', 'applications', { statusFilter, startDate, endDate }],
    queryFn: () => {
      const query = buildReworkListQuery({ statusFilter, startDate, endDate });
      return api.get<ReworkApplication[]>(`/rework/applications?${query}`)
        .then((response) => response.data);
    },
  });

  const statsQuery = useQuery({
    queryKey: ['rework', 'statistics'],
    queryFn: () => api.get<ReworkStatistics>('/rework/statistics').then((response) => response.data),
  });

  // 供 ReworkPage 在 mutation 成功後重載列表與統計；
  // 只失效精確 key（非寬 prefix），queryClient 參考穩定所以本函數參考也穩定
  const loadData = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ['rework', 'applications'] });
    await queryClient.invalidateQueries({ queryKey: ['rework', 'statistics'] });
  }, [queryClient]);

  return {
    applications: listQuery.data ?? [],
    stats: statsQuery.data ?? null,
    loading: listQuery.isPending || statsQuery.isPending,
    loadData,
    isSuccess: listQuery.isSuccess && statsQuery.isSuccess,
  };
};
