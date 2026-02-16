import { Bar, Doughnut } from 'react-chartjs-2';
import '../../utils/chartSetup';
import type { ReworkStatistics } from '../../types';

interface Props {
    stats: ReworkStatistics | null;
}

const ReworkStatisticsDashboard = ({ stats }: Props) => {
    if (!stats) return null;

    const { application_stats, department_stats, cost_stats } = stats;

    const deptChartData = {
        labels: department_stats.map(d => d.department || '未分類'),
        datasets: [
            {
                label: '申請數量',
                data: department_stats.map(d => d.count),
                backgroundColor: 'rgba(54, 162, 235, 0.6)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 1,
            },
        ],
    };

    const costChartData = {
        labels: ['人工成本', '材料成本', '設備成本'],
        datasets: [
            {
                data: [
                    Number(cost_stats?.labor_cost) || 0,
                    Number(cost_stats?.material_cost) || 0,
                    Number(cost_stats?.equipment_cost) || 0,
                ],
                backgroundColor: [
                    'rgba(255, 99, 132, 0.6)',
                    'rgba(54, 162, 235, 0.6)',
                    'rgba(255, 206, 86, 0.6)',
                ],
                borderColor: [
                    'rgba(255, 99, 132, 1)',
                    'rgba(54, 162, 235, 1)',
                    'rgba(255, 206, 86, 1)',
                ],
                borderWidth: 1,
            },
        ],
    };

    const hasCostData = (cost_stats?.labor_cost || cost_stats?.material_cost || cost_stats?.equipment_cost) > 0;

    return (
        <div className="mb-4">
            {/* Summary Cards */}
            <div className="row mb-4">
                <div className="col-md-3">
                    <div className="card text-white bg-primary mb-3 h-100 shadow-sm">
                        <div className="card-body text-center">
                            <h3 className="display-4 fw-bold">{application_stats.total_applications || 0}</h3>
                            <p className="card-text fs-5">總申請數</p>
                        </div>
                    </div>
                </div>
                <div className="col-md-3">
                    <div className="card text-white bg-warning mb-3 h-100 shadow-sm">
                        <div className="card-body text-center">
                            <h3 className="display-4 fw-bold">{application_stats.in_progress || 0}</h3>
                            <p className="card-text fs-5">執行中</p>
                        </div>
                    </div>
                </div>
                <div className="col-md-3">
                    <div className="card text-white bg-success mb-3 h-100 shadow-sm">
                        <div className="card-body text-center">
                            <h3 className="display-4 fw-bold">{application_stats.completed || 0}</h3>
                            <p className="card-text fs-5">已完成</p>
                        </div>
                    </div>
                </div>
                <div className="col-md-3">
                    <div className="card text-white bg-danger mb-3 h-100 shadow-sm">
                        <div className="card-body text-center">
                            <h3 className="display-4 fw-bold">
                                ${cost_stats.total_cost?.toLocaleString() || 0}
                            </h3>
                            <p className="card-text fs-5">總成本</p>
                        </div>
                    </div>
                </div>
            </div>

            {/* Charts */}
            <div className="row">
                <div className="col-md-8">
                    <div className="card shadow-sm h-100">
                        <div className="card-header bg-white fw-bold">部門申請統計</div>
                        <div className="card-body">
                            <Bar
                                data={deptChartData}
                                options={{
                                    responsive: true,
                                    plugins: { legend: { position: 'top' as const } }
                                }}
                            />
                        </div>
                    </div>
                </div>
                <div className="col-md-4">
                    <div className="card shadow-sm h-100">
                        <div className="card-header bg-white fw-bold">成本分佈</div>
                        <div className="card-body">
                            {hasCostData ? (
                                <Doughnut
                                    data={costChartData}
                                    options={{
                                        responsive: true,
                                        plugins: { legend: { position: 'bottom' as const } }
                                    }}
                                />
                            ) : (
                                <div className="d-flex align-items-center justify-content-center h-100 text-muted">
                                    <p className="mb-0">尚無成本資料</p>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ReworkStatisticsDashboard;
