import { memo } from 'react';
import { useDashboardStats } from '../../hooks/useDashboard';
import type { DatePeriod } from '../../hooks/useDashboard';
import type { DashboardStats } from '../../types';

interface KPICardsProps {
    period?: DatePeriod;
    customDateRange?: { start: string; end: string };
}

type KpiGetter = (stats: DashboardStats) => number;
// trend 實際上是 string（API 回傳），使用 string 型別避免不必要的斷言
type KpiTrendGetter = (stats: DashboardStats) => string;
type KpiChangeGetter = (stats: DashboardStats) => number;
type KpiAnomalyGetter = (stats: DashboardStats) => boolean;
type NgInfoGetter = (stats: DashboardStats) => { rate: number | null; count: number };

interface KpiItemConfig {
    label: string;
    key: keyof DashboardStats;
    icon: string;
    getValue: KpiGetter;
    getPending: KpiGetter;
    getTrend: KpiTrendGetter;
    getChange: KpiChangeGetter;
    path: string;
    suffix?: string;
    isAnomaly: KpiAnomalyGetter;
    getNgInfo?: NgInfoGetter;
}

const KPICards = ({ period = 'this_month', customDateRange }: KPICardsProps) => {
    const { stats, loading } = useDashboardStats(period, customDateRange);

    const kpiItems: KpiItemConfig[] = [
        {
            label: '出貨檢驗',
            key: 'shipping',
            icon: 'fa-gift',
            getValue: (s) => s.shipping.current,
            getPending: (s) => s.shipping.pending,
            getTrend: (s) => s.shipping.trend,
            getChange: (s) => s.shipping.change_pct,
            path: '/shipping',
            isAnomaly: () => false,
            getNgInfo: (s) => ({
                rate: s.shipping.ng_rate ?? null,
                count: s.shipping.ng_count ?? 0,
            }),
        },
        {
            label: '現場巡檢',
            key: 'patrol',
            icon: 'fa-wand-magic-sparkles',
            getValue: (s) => s.patrol.current,
            getPending: (s) => s.patrol.pending,
            getTrend: (s) => s.patrol.trend,
            getChange: (s) => s.patrol.change_pct,
            path: '/patrol',
            isAnomaly: () => false,
            getNgInfo: (s) => ({
                rate: s.patrol.ng_rate ?? null,
                count: s.patrol.ng_count ?? 0,
            }),
        },
        {
            label: '不合格品',
            key: 'ncmr',
            icon: 'fa-triangle-exclamation',
            getValue: (s) => s.ncmr.pending,
            getPending: (s) => s.ncmr.pending,
            getTrend: (s) => s.ncmr.trend,
            getChange: (s) => s.ncmr.change_pct,
            path: '/ncmr',
            suffix: '待處理',
            isAnomaly: (s) => (s.ncmr.trend === 'up' && s.ncmr.change_pct > 20)
        },
        {
            label: '重工申請',
            key: 'rework',
            icon: 'fa-rotate',
            getValue: (s) => s.rework.pending,
            getPending: (s) => s.rework.pending,
            getTrend: (s) => s.rework.trend,
            getChange: (s) => s.rework.change_pct,
            path: '/rework',
            suffix: '待處理',
            isAnomaly: (s) => (s.rework.trend === 'up' && s.rework.change_pct > 30)
        },
        {
            label: 'CAR 要求',
            key: 'cara',
            icon: 'fa-bullhorn',
            getValue: (s) => s.cara.pending,
            getPending: (s) => s.cara.pending,
            getTrend: (s) => s.cara.trend,
            getChange: (s) => s.cara.change_pct,
            path: '/cara',
            suffix: '待處理',
            isAnomaly: (s) => (s.cara.trend === 'up' && s.cara.change_pct > 30)
        },
        {
            label: '矯正措施',
            key: 'capa',
            icon: 'fa-file-signature',
            getValue: (s) => s.capa.pending,
            getPending: (s) => s.capa.pending,
            getTrend: (s) => s.capa.trend,
            getChange: (s) => s.capa.change_pct,
            path: '/capa',
            suffix: '進行中',
            isAnomaly: (s) => (s.capa.trend === 'up' && s.capa.change_pct > 30)
        }
    ];

    const getTrendIcon = (trend: string, change: number) => {
        if (trend === 'up') {
            return <span className="trend-up">↑ {Math.abs(change)}%</span>;
        } else if (trend === 'down') {
            return <span className="trend-down">↓ {Math.abs(change)}%</span>;
        }
        return <span className="trend-stable">→ 持平</span>;
    };

    if (loading) {
        return (
            <div className="row g-4 mb-4">
                {[1, 2, 3, 4, 5, 6].map(i => (
                    <div key={i} className="col-6 col-lg-4">
                        <div className="card kpi-card-skeleton">
                            <div className="card-body">
                                <div className="skeleton-title"></div>
                                <div className="skeleton-value"></div>
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        );
    }

    if (!stats) {
        return (
            <div className="alert alert-warning">載入失敗，請重新整理頁面</div>
        );
    }

    return (
        <div className="row g-3 g-lg-4 mb-4">
            {kpiItems.map(item => {
                const value = item.getValue(stats);
                const trend = item.getTrend(stats);
                const change = item.getChange(stats);
                const isAnomaly = item.isAnomaly(stats);

                return (
                    <div key={item.key} className="col-6 col-lg-4">
                        <a 
                            href={item.path}
                            className="text-decoration-none"
                            onClick={(e) => {
                                e.preventDefault();
                                window.location.href = item.path;
                            }}
                        >
                            <div 
                                className={`kpi-card h-100 kpi-${item.key}`}
                                style={{ borderRadius: '16px', padding: '16px' }}
                            >
                                <div style={{ color: 'white' }}>
                                    <div className="d-flex justify-content-between align-items-start mb-2">
                                        <div className="kpi-icon">
                                            <i className={`fa-solid ${item.icon}`}></i>
                                        </div>
                                        {isAnomaly && (
                                            <span className="kpi-alert" title="異常飆高">⚠️</span>
                                        )}
                                    </div>
                                    <div className="kpi-value">
                                        {value}
                                        {item.suffix && <span className="kpi-suffix">{item.suffix}</span>}
                                    </div>
                                    <div className="kpi-label">{item.label}</div>
                                    <div className="kpi-trend">
                                        {item.getNgInfo ? (
                                            (() => {
                                                const { rate, count } = item.getNgInfo(stats);
                                                if (rate === null) {
                                                    return <span style={{ color: '#94a3b8' }}>—</span>;
                                                }
                                                if (rate === 0) {
                                                    return <span style={{ color: '#22c55e', fontWeight: 600 }}>✓ 全數合格</span>;
                                                }
                                                const isHigh = rate > 5;
                                                return (
                                                    <span style={{ color: isHigh ? '#ef4444' : '#22c55e', fontWeight: 600 }}>
                                                        {isHigh ? '⚠ ' : '✓ '}超差率 {rate}%（{count} 筆）
                                                    </span>
                                                );
                                            })()
                                        ) : (
                                            getTrendIcon(trend, change)
                                        )}
                                    </div>
                                </div>
                            </div>
                        </a>
                    </div>
                );
            })}
        </div>
    );
};

export default memo(KPICards);
