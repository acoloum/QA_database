import { useState, useEffect } from 'react';
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
    type: 'ncmr' | 'capa' | 'rework';
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
    const [stats, setStats] = useState<DashboardStats | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [dateRange, setDateRange] = useState<{ start: string; end: string } | null>(null);

    useEffect(() => {
        let cancelled = false;

        const fetchStats = async () => {
            try {
                setLoading(true);
                const params: Record<string, string> = { period };

                if (period === 'custom' && customDateRange) {
                    params.start = customDateRange.start;
                    params.end = customDateRange.end;
                }

                const response = await api.get('/dashboard/stats', { params });
                if (!cancelled) {
                    setStats(response.data.stats);
                    setDateRange({ start: response.data.start_date, end: response.data.end_date });
                }
            } catch (err) {
                if (!cancelled) setError('Failed to load statistics');
                console.error(err);
            } finally {
                if (!cancelled) setLoading(false);
            }
        };

        fetchStats();

        return () => { cancelled = true; };
    }, [period, customDateRange]);

    return { stats, loading, error, dateRange };
}

export function useDashboardTodos() {
    const [todos, setTodos] = useState<TodoItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;

        const fetchTodos = async () => {
            try {
                setLoading(true);
                const response = await api.get('/dashboard/todos');
                if (!cancelled) setTodos(response.data);
            } catch (err) {
                if (!cancelled) setError('Failed to load todos');
                console.error(err);
            } finally {
                if (!cancelled) setLoading(false);
            }
        };

        fetchTodos();

        return () => { cancelled = true; };
    }, []);

    return { todos, loading, error };
}

export function useDashboardTrends() {
    const [trends, setTrends] = useState<DashboardTrends | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;

        const fetchTrends = async () => {
            try {
                setLoading(true);
                const response = await api.get('/dashboard/trends');
                if (!cancelled) setTrends(response.data);
            } catch (err) {
                if (!cancelled) setError('Failed to load trends');
                console.error(err);
            } finally {
                if (!cancelled) setLoading(false);
            }
        };

        fetchTrends();

        return () => { cancelled = true; };
    }, []);

    return { trends, loading, error };
}
