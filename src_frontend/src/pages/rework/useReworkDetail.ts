import { useCallback, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../../services/api';
import { reworkKeys } from '../../hooks/queryKeys';
import type {
  ReworkApplication,
  ReworkCostDetail,
  ReworkExecutionDetail,
  ReworkInspectionDetail,
} from '../../types';

export type ReworkDetailTab = 'basic' | 'execution' | 'inspection' | 'cost';

export const useReworkDetail = (afterReload: () => Promise<void>) => {
  const queryClient = useQueryClient();
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [selectedReworkDetailId, setSelectedReworkDetailId] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<ReworkDetailTab>('basic');

  // 伺服器資料統一由 React Query 管理（取代手動 useState + fetch），
  // query key 含 reworkId，切換單據時各自獨立快取，不互相污染。
  // staleTime 沿用 main.tsx 全域設定（30 秒），不在此重複覆寫。
  const enabled = showDetailModal && selectedReworkDetailId != null;

  const { data: selectedReworkDetail } = useQuery({
    queryKey: reworkKeys.application(selectedReworkDetailId),
    queryFn: async () => {
      if (selectedReworkDetailId == null) return null;
      const res = await api.get<{ data: ReworkApplication[] }>(
        `/rework/applications?rework_id=${selectedReworkDetailId}`,
      );
      return res.data?.data?.[0] ?? null;
    },
    enabled,
  });

  const executionsQuery = useQuery({
    queryKey: reworkKeys.executions(selectedReworkDetailId),
    queryFn: async () => {
      if (selectedReworkDetailId == null) return [] as ReworkExecutionDetail[];
      const res = await api.get<ReworkExecutionDetail[]>(
        `/rework/executions?rework_id=${selectedReworkDetailId}`,
      );
      return res.data || [];
    },
    enabled,
  });

  const inspectionsQuery = useQuery({
    queryKey: reworkKeys.inspections(selectedReworkDetailId),
    queryFn: async () => {
      if (selectedReworkDetailId == null) return [] as ReworkInspectionDetail[];
      const res = await api.get<ReworkInspectionDetail[]>(
        `/rework/inspections?rework_id=${selectedReworkDetailId}`,
      );
      return res.data || [];
    },
    enabled,
  });

  const costsQuery = useQuery({
    queryKey: reworkKeys.costs(selectedReworkDetailId),
    queryFn: async () => {
      if (selectedReworkDetailId == null) return [] as ReworkCostDetail[];
      const res = await api.get<ReworkCostDetail[]>(
        `/rework/costs?rework_id=${selectedReworkDetailId}`,
      );
      return res.data || [];
    },
    enabled,
  });

  const openDetail = useCallback((item: ReworkApplication) => {
    // 以列表頁既有的 item 預填 application 快取，詳情 Modal 開啟時立即顯示（不閃 loading），
    // 同時背景重新抓取以取得最新資料。
    setSelectedReworkDetailId(item.識別碼);
    queryClient.setQueryData(reworkKeys.application(item.識別碼), item);
    setShowDetailModal(true);
    setActiveTab('basic');
  }, [queryClient]);

  const reloadDetailData = useCallback(async () => {
    if (selectedReworkDetailId == null) return;
    // invalidateQueries 於 v5 會等待 active query 重新抓取完成後 resolve
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: reworkKeys.application(selectedReworkDetailId) }),
      queryClient.invalidateQueries({ queryKey: reworkKeys.executions(selectedReworkDetailId) }),
      queryClient.invalidateQueries({ queryKey: reworkKeys.inspections(selectedReworkDetailId) }),
      queryClient.invalidateQueries({ queryKey: reworkKeys.costs(selectedReworkDetailId) }),
    ]);
    await afterReload();
  }, [afterReload, queryClient, selectedReworkDetailId]);

  return {
    showDetailModal,
    setShowDetailModal,
    // useQuery 未載入時 data 為 undefined，對外收斂為 null 以符合既有呼叫端型別
    selectedReworkDetail: selectedReworkDetail ?? null,
    executions: executionsQuery.data ?? [],
    inspections: inspectionsQuery.data ?? [],
    costs: costsQuery.data ?? [],
    activeTab,
    setActiveTab,
    openDetail,
    reloadDetailData,
  };
};
