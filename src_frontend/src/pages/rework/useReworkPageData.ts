import { useCallback, useEffect, useState } from 'react';
import api from '../../services/api';
import type { ReworkApplication, ReworkStatistics } from '../../types';
import { buildReworkListQuery } from './reworkPageUtils';

interface UseReworkPageDataParams {
  statusFilter: string;
  startDate: string;
  endDate: string;
}

export const useReworkPageData = ({ statusFilter, startDate, endDate }: UseReworkPageDataParams) => {
  const [applications, setApplications] = useState<ReworkApplication[]>([]);
  const [stats, setStats] = useState<ReworkStatistics | null>(null);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const query = buildReworkListQuery({ statusFilter, startDate, endDate });
      const [listRes, statsRes] = await Promise.all([
        api.get<ReworkApplication[]>(`/rework/applications?${query}`),
        api.get<ReworkStatistics>('/rework/statistics'),
      ]);
      setApplications(listRes.data);
      setStats(statsRes.data);
    } catch (error) {
      console.error('Error loading rework data:', error);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, startDate, endDate]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  return {
    applications,
    stats,
    loading,
    loadData,
  };
};
