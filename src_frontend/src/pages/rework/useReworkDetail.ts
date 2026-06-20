import { useCallback, useState } from 'react';
import api from '../../services/api';
import type {
  ReworkApplication,
  ReworkCostDetail,
  ReworkExecutionDetail,
  ReworkInspectionDetail,
} from '../../types';

export type ReworkDetailTab = 'basic' | 'execution' | 'inspection' | 'cost';

export const useReworkDetail = (afterReload: () => Promise<void>) => {
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [selectedReworkDetail, setSelectedReworkDetail] = useState<ReworkApplication | null>(null);
  const [executions, setExecutions] = useState<ReworkExecutionDetail[]>([]);
  const [inspections, setInspections] = useState<ReworkInspectionDetail[]>([]);
  const [costs, setCosts] = useState<ReworkCostDetail[]>([]);
  const [activeTab, setActiveTab] = useState<ReworkDetailTab>('basic');

  const loadDetailRecords = useCallback(async (reworkId: number) => {
    const [execRes, inspRes, costRes] = await Promise.all([
      api.get<ReworkExecutionDetail[]>(`/rework/executions?rework_id=${reworkId}`),
      api.get<ReworkInspectionDetail[]>(`/rework/inspections?rework_id=${reworkId}`),
      api.get<ReworkCostDetail[]>(`/rework/costs?rework_id=${reworkId}`),
    ]);
    setExecutions(execRes.data || []);
    setInspections(inspRes.data || []);
    setCosts(costRes.data || []);
  }, []);

  const openDetail = useCallback(async (item: ReworkApplication) => {
    setSelectedReworkDetail(item);
    setShowDetailModal(true);
    setActiveTab('basic');

    try {
      await loadDetailRecords(item.識別碼);
    } catch (error) {
      console.error('Failed to load rework detail data', error);
      setExecutions([]);
      setInspections([]);
      setCosts([]);
    }
  }, [loadDetailRecords]);

  const reloadDetailData = useCallback(async () => {
    if (!selectedReworkDetail) return;
    const reworkId = selectedReworkDetail.識別碼;
    try {
      const appRes = await api.get<ReworkApplication[]>(`/rework/applications?rework_id=${reworkId}`);
      if (appRes.data && appRes.data.length > 0) {
        setSelectedReworkDetail(appRes.data[0]);
      }
      await loadDetailRecords(reworkId);
      await afterReload();
    } catch (error) {
      console.error('Failed to reload rework detail data', error);
    }
  }, [afterReload, loadDetailRecords, selectedReworkDetail]);

  return {
    showDetailModal,
    setShowDetailModal,
    selectedReworkDetail,
    executions,
    inspections,
    costs,
    activeTab,
    setActiveTab,
    openDetail,
    reloadDetailData,
  };
};
