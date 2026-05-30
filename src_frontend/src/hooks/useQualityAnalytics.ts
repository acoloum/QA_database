import { useQuery } from '@tanstack/react-query';
import api from '../services/api';

export interface AnalyticsDateParams {
    date_from?: string;
    date_to?: string;
}

export interface ParetoItem {
    label: string;
    count: number;
    pct: number;
    cumulative_pct: number;
}

export interface ParetoResult {
    source: string;
    field: string;
    total: number;
    items: ParetoItem[];
}

export interface DefectTrendSeries {
    label: string;
    data: number[];
}

export interface DefectTrendResult {
    source: string;
    months: string[];
    series: DefectTrendSeries[];
}

export interface CapaAgingResult {
    buckets: Record<'0-7' | '8-14' | '15-30' | '31+', number>;
    open_count: number;
    overdue_count: number;
    overdue_items: {
        id: number;
        number: string;
        status: string;
        age_days: number;
        deadline: string;
        overdue_days: number;
    }[];
    avg_close_days: number | null;
}

export interface RepeatIssuesResult {
    ncmr: {
        vendor: string;
        material: string;
        product_info: string;
        defect_category: string;
        defect_detail: string;
        count: number;
        latest_date: string | null;
        numbers: string[];
    }[];
    complaints: {
        id: number;
        complaint_no: string;
        customer: string;
        defect_category: string;
        complaint_date: string | null;
        repeat_refs: string[];
    }[];
}

export interface VendorRankingItem {
    vendor_id: number;
    vendor_name: string;
    period: string;
    inspection_count: number;
    defect_count: number;
    defect_rate: number;
    capa_count: number;
    avg_capa_days: number | null;
    complaint_count: number;
    score: number;
}

const cleanParams = (params: Record<string, string | number | undefined>) =>
    Object.fromEntries(Object.entries(params).filter(([, value]) => value !== undefined && value !== ''));

export const usePareto = (source: 'ncmr' | 'complaint', params: AnalyticsDateParams) =>
    useQuery({
        queryKey: ['qualityAnalytics', 'pareto', source, params],
        queryFn: async () => {
            const res = await api.get<{ data: ParetoResult }>('/quality-analytics/pareto', {
                params: cleanParams({ ...params, source, field: 'category', limit: 10 }),
            });
            return res.data.data;
        },
    });

export const useDefectTrends = (source: 'ncmr' | 'complaint', params: AnalyticsDateParams) =>
    useQuery({
        queryKey: ['qualityAnalytics', 'defectTrends', source, params],
        queryFn: async () => {
            const res = await api.get<{ data: DefectTrendResult }>('/quality-analytics/defect-trends', {
                params: cleanParams({ ...params, source, top_n: 5 }),
            });
            return res.data.data;
        },
    });

export const useCapaAging = () =>
    useQuery({
        queryKey: ['qualityAnalytics', 'capaAging'],
        queryFn: async () => {
            const res = await api.get<{ data: CapaAgingResult }>('/quality-analytics/capa-aging');
            return res.data.data;
        },
    });

export const useRepeatIssues = (params: AnalyticsDateParams) =>
    useQuery({
        queryKey: ['qualityAnalytics', 'repeatIssues', params],
        queryFn: async () => {
            const res = await api.get<{ data: RepeatIssuesResult }>('/quality-analytics/repeat-issues', {
                params: cleanParams({ ...params, limit: 10 }),
            });
            return res.data.data;
        },
    });

export const useVendorRanking = (period: string) =>
    useQuery({
        queryKey: ['qualityAnalytics', 'vendorRanking', period],
        queryFn: async () => {
            const res = await api.get<{ data: VendorRankingItem[] }>('/quality-analytics/vendor-ranking', {
                params: { period, limit: 10 },
            });
            return res.data.data;
        },
    });
