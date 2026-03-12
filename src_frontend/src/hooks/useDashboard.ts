import { useQuery } from '@tanstack/react-query';
import api from '../services/api';

export interface DashboardStats {
    shipping: { current: number; previous: number; pending: number; trend: string; change_pct: number };
    patrol: { current: number; previous: number; pending: number; trend: string; change_pct: number };
    ncmr: { current: number; previous: number; pending: number; trend: string; change_pct: number };
    capa: { current: number; previous: number; pending: number; trend: string; change_pct: number };
    rework: { current: number; previous: number; pending: number; trend: string; change_pct: number };
    cara: { current: number; previous: number; pending: number; trend: string; change_pct: number };
}

export interface TodoItem {
    type: 'ncmr' | 'capa' | 'rework' | 'cara';
    id: string;
    title: string;
    description: string | null;
    date: string | null;
    priority: 'high' | 'medium' | 'low';
    path: string;
}

export interface TrendData {
    month: string;
    count: number;
}

export interface DashboardTrends {
    ncmr_by_month: TrendData[];
    shipping_ok_by_month: TrendData[];
    shipping_ng_by_month: TrendData[];
    rework_by_month: TrendData[];
}

export type DatePeriod = 'this_week' | 'this_month' | 'last_month' | 'custom';

export function useDashboardStats(period: DatePeriod = 'this_month', customDateRange?: { start: string; end: string }) {
    const query = useQuery({
        queryKey: ['dashboardStats', period, customDateRange],
        queryFn: async () => {
            const params: Record<string, string> = { period };
            if (period === 'custom' && customDateRange) {
                params.start = customDateRange.start;
                params.end = customDateRange.end;
            }
            const { data } = await api.get('/dashboard/stats', { params });
            return data;
        },
        staleTime: 5 * 60 * 1000 // 5 minutes cache
    });

    return {
        stats: query.data?.stats as DashboardStats | null,
        loading: query.isLoading,
        error: query.isError ? 'Failed to load statistics' : null,
        dateRange: query.data ? { start: query.data.start_date, end: query.data.end_date } : null
    };
}

export function useDashboardTodos() {
    const query = useQuery({
        queryKey: ['dashboardTodos'],
        queryFn: async () => {
            const { data } = await api.get('/dashboard/todos');
            return data as TodoItem[];
        },
        staleTime: 60 * 1000 // 1 min cache
    });

    return { 
        todos: query.data || [], 
        loading: query.isLoading, 
        error: query.isError ? 'Failed to load todos' : null 
    };
}

export function useDashboardTrends() {
    const query = useQuery({
        queryKey: ['dashboardTrends'],
        queryFn: async () => {
            const { data } = await api.get('/dashboard/trends');
            return data as DashboardTrends;
        },
        staleTime: 5 * 60 * 1000
    });

    return { 
        trends: query.data || null, 
        loading: query.isLoading, 
        error: query.isError ? 'Failed to load trends' : null 
    };
}
