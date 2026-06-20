// 儀表板統計型別
export type TrendDirection = 'up' | 'down' | 'stable';

// KPI 模組統計資料，trend 使用 string 相容 useDashboard hook 回傳的任意字串
export interface KpiModuleStats {
    current: number;
    previous?: number;
    pending: number;
    trend: string; // useDashboard hook 回傳 string，非嚴格限定 TrendDirection
    change_pct: number;
    ng_rate?: number | null;
    ng_count?: number;
}

export interface DashboardStats {
    shipping: KpiModuleStats;
    patrol: KpiModuleStats;
    ncmr: KpiModuleStats;
    rework: KpiModuleStats;
    capa: KpiModuleStats;
}

