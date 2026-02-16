import { useDashboardTrends } from '../../hooks/useDashboard';
import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    Legend,
    Filler
} from 'chart.js';
import { Line } from 'react-chartjs-2';

ChartJS.register(
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    Legend,
    Filler
);

const TrendChart = () => {
    const { trends, loading, error } = useDashboardTrends();

    if (loading) {
        return (
            <div className="card mb-4">
                <div className="card-header">
                    <i className="fa-solid fa-chart-line me-2 text-success"></i>
                    <span className="fw-bold">趨勢分析</span>
                </div>
                <div className="card-body">
                    <div className="chart-skeleton" style={{ height: '300px' }}></div>
                </div>
            </div>
        );
    }

    if (error || !trends) {
        return null;
    }

    const labels = trends.ncmr_by_month.map(item => item.month);

    const data = {
        labels,
        datasets: [
            {
                label: '不合格品 (NCMR)',
                data: trends.ncmr_by_month.map(item => item.count),
                borderColor: '#ef4444',
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                fill: true,
                tension: 0.4,
                pointRadius: 4,
                pointHoverRadius: 6
            },
            {
                label: '重工申請',
                data: trends.rework_by_month.map(item => item.count),
                borderColor: '#14b8a6',
                backgroundColor: 'rgba(20, 184, 166, 0.1)',
                fill: true,
                tension: 0.4,
                pointRadius: 4,
                pointHoverRadius: 6
            },
            {
                label: '出貨檢驗',
                data: trends.shipping_by_month.map(item => item.count),
                borderColor: '#f97316',
                backgroundColor: 'rgba(249, 115, 22, 0.1)',
                fill: true,
                tension: 0.4,
                pointRadius: 4,
                pointHoverRadius: 6
            }
        ]
    };

    const options = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: 'top' as const,
                labels: {
                    usePointStyle: true,
                    padding: 20,
                    font: {
                        family: "'Inter', sans-serif",
                        size: 12
                    }
                }
            },
            tooltip: {
                backgroundColor: 'rgba(30, 41, 59, 0.9)',
                titleFont: {
                    family: "'Inter', sans-serif",
                    size: 13
                },
                bodyFont: {
                    family: "'Inter', sans-serif",
                    size: 12
                },
                padding: 12,
                cornerRadius: 8
            }
        },
        scales: {
            x: {
                grid: {
                    display: false
                },
                ticks: {
                    font: {
                        family: "'Inter', sans-serif",
                        size: 11
                    }
                }
            },
            y: {
                beginAtZero: true,
                grid: {
                    color: 'rgba(0, 0, 0, 0.05)'
                },
                ticks: {
                    font: {
                        family: "'Inter', sans-serif",
                        size: 11
                    },
                    stepSize: 1
                }
            }
        },
        interaction: {
            intersect: false,
            mode: 'index' as const
        }
    };

    return (
        <div className="card mb-4">
            <div className="card-header d-flex align-items-center">
                <i className="fa-solid fa-chart-line me-2 text-success"></i>
                <span className="fw-bold">趨勢分析</span>
                <span className="text-muted ms-2" style={{ fontSize: '0.8rem' }}>(近半年)</span>
            </div>
            <div className="card-body">
                <div style={{ height: '300px' }}>
                    <Line data={data} options={options} />
                </div>
            </div>
        </div>
    );
};

export default TrendChart;
