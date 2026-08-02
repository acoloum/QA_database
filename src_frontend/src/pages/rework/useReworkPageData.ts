import { useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../../services/api';
import type { ReworkApplication, ReworkStatistics } from '../../types';
import { buildReworkListQuery } from './reworkPageUtils';
import { reworkKeys } from '../../hooks/queryKeys';

interface UseReworkPageDataParams {
  statusFilter: string;
  startDate: string;
  endDate: string;
  page?: number;
}

/** /rework/applications 的分頁回應，與出貨檢驗清單同一形狀。 */
interface ReworkApplicationPage {
  data: ReworkApplication[];
  total: number;
  total_pages: number;
}

export const useReworkPageData = ({
  statusFilter,
  startDate,
  endDate,
  page = 1,
}: UseReworkPageDataParams) => {
  const queryClient = useQueryClient();

  // 列表與統計改用 useQuery 註冊快取；篩選條件變更時由 query key 驅動重新載入
  const listQuery = useQuery({
    queryKey: reworkKeys.applications({ statusFilter, startDate, endDate, page }),
    queryFn: () => {
      return api.get<ReworkApplicationPage>('/rework/applications', {
        params: { ...buildReworkListQuery({ statusFilter, startDate, endDate }), page },
      }).then((response) => response.data);
    },
    // 換頁時沿用上一頁資料，避免表格閃爍成空白
    placeholderData: (previousData) => previousData,
  });

  const statsQuery = useQuery({
    queryKey: reworkKeys.statistics,
    queryFn: () => api.get<ReworkStatistics>('/rework/statistics').then((response) => response.data),
  });

  // 供 ReworkPage 在 mutation 成功後重載列表與統計；
  // 只失效精確 key（非寬 prefix），queryClient 參考穩定所以本函數參考也穩定
  const loadData = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: reworkKeys.applicationsRoot });
    await queryClient.invalidateQueries({ queryKey: reworkKeys.statistics });
  }, [queryClient]);

  return {
    applications: listQuery.data?.data ?? [],
    totalPages: listQuery.data?.total_pages ?? 1,
    total: listQuery.data?.total ?? 0,
    stats: statsQuery.data ?? null,
    loading: listQuery.isPending || statsQuery.isPending,
    loadData,
    isSuccess: listQuery.isSuccess && statsQuery.isSuccess,
  };
};
