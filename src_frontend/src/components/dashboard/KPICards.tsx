import { memo } from 'react';
import { useDashboardStats } from '../../hooks/useDashboard';
import type { DatePeriod } from '../../hooks/useDashboard';

interface KPICardsProps {
    period?: DatePeriod;
    customDateRange?: { start: string; end: string };
}

const KPICards = ({ period = 'this_month', customDateRange }: KPICardsProps) => {
    const { stats, loading } = useDashboardStats(period, customDateRange);

    const kpiItems = [
        {
            label: '出貨檢驗',
            key: 'shipping',
            icon: 'fa-gift',
            getValue: (s: any) => s?.shipping?.current || 0,
            getPending: (s: any) => s?.shipping?.pending || 0,
            getTrend: (s: any) => s?.shipping?.trend || 'stable',
            getChange: (s: any) => s?.shipping?.change_pct || 0,
            path: '/shipping',
            isAnomaly: () => false,
            getNgInfo: (s: any) => ({
                rate: s?.shipping?.ng_rate ?? null,
                count: s?.shipping?.ng_count ?? 0,
            }),
        },
        {
            label: '現場巡檢',
            key: 'patrol',
            icon: 'fa-wand-magic-sparkles',
            getValue: (s: any) => s?.patrol?.current || 0,
            getPending: (s: any) => s?.patrol?.pending || 0,
            getTrend: (s: any) => s?.patrol?.trend || 'stable',
            getChange: (s: any) => s?.patrol?.change_pct || 0,
            path: '/patrol',
            isAnomaly: () => false
        },
        {
            label: '不合格品',
            key: 'ncmr',
            icon: 'fa-triangle-exclamation',
            getValue: (s: any) => s?.ncmr?.pending || 0,
            getPending: (s: any) => s?.ncmr?.pending || 0,
            getTrend: (s: any) => s?.ncmr?.trend || 'stable',
            getChange: (s: any) => s?.ncmr?.change_pct || 0,
            path: '/ncmr',
            suffix: '待處理',
            isAnomaly: (s: any) => (s?.ncmr?.trend === 'up' && s?.ncmr?.change_pct > 20)
        },
        {
            label: '重工申請',
            key: 'rework',
            icon: 'fa-rotate',
            getValue: (s: any) => s?.rework?.pending || 0,
            getPending: (s: any) => s?.rework?.pending || 0,
            getTrend: (s: any) => s?.rework?.trend || 'stable',
            getChange: (s: any) => s?.rework?.change_pct || 0,
            path: '/rework',
            suffix: '待處理',
            isAnomaly: (s: any) => (s?.rework?.trend === 'up' && s?.rework?.change_pct > 30)
        },
        {
            label: 'CAR 要求',
            key: 'cara',
            icon: 'fa-bullhorn',
            getValue: (s: any) => s?.cara?.pending || 0,
            getPending: (s: any) => s?.cara?.pending || 0,
            getTrend: (s: any) => s?.cara?.trend || 'stable',
            getChange: (s: any) => s?.cara?.change_pct || 0,
            path: '/cara',
            suffix: '待處理',
            isAnomaly: (s: any) => (s?.cara?.trend === 'up' && s?.cara?.change_pct > 30)
        },
        {
            label: '矯正措施',
            key: 'capa',
            icon: 'fa-file-signature',
            getValue: (s: any) => s?.capa?.pending || 0,
            getPending: (s: any) => s?.capa?.pending || 0,
            getTrend: (s: any) => s?.capa?.trend || 'stable',
            getChange: (s: any) => s?.capa?.change_pct || 0,
            path: '/capa',
            suffix: '進行中',
            isAnomaly: (s: any) => (s?.capa?.trend === 'up' && s?.capa?.change_pct > 30)
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
                                        {(item as any).getNgInfo ? (
                                            (() => {
                                                const { rate, count } = (item as any).getNgInfo(stats);
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
