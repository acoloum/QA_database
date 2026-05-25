import { useState } from 'react';
import { Row, Col } from 'react-bootstrap';
import WelcomeMessage from '../components/dashboard/WelcomeMessage';
import KPICards from '../components/dashboard/KPICards';
import QuickActions from '../components/dashboard/QuickActions';
import TodoList from '../components/dashboard/TodoList';
import TrendChart from '../components/dashboard/TrendChart';
import DateFilter from '../components/dashboard/DateFilter';
import MyTasksWidget from '../components/common/MyTasksWidget';
import OverdueCapaWidget from '../components/dashboard/OverdueCapaWidget';
import OverdueComplaintWidget from '../components/dashboard/OverdueComplaintWidget';
import RecentRepeatsWidget from '../components/dashboard/RecentRepeatsWidget';
import { useDashboardStats } from '../hooks/useDashboard';
import type { DatePeriod } from '../hooks/useDashboard';

const DashboardPage = () => {
    const [period, setPeriod] = useState<DatePeriod>('this_month');
    const [customDateRange, setCustomDateRange] = useState<{ start: string; end: string } | undefined>();

    const { dateRange } = useDashboardStats(period, customDateRange);

    const formatDateRange = () => {
        if (!dateRange) return '';
        const start = new Date(dateRange.start).toLocaleDateString('zh-TW', { month: 'short', day: 'numeric' });
        const end = new Date(dateRange.end).toLocaleDateString('zh-TW', { month: 'short', day: 'numeric' });
        return `${start} - ${end}`;
    };

    return (
        <div className="dashboard-container">
            <WelcomeMessage />

            <DateFilter
                period={period}
                onPeriodChange={setPeriod}
                customDateRange={customDateRange}
                onCustomDateChange={setCustomDateRange}
                dateRangeLabel={formatDateRange()}
            />

            <KPICards period={period} customDateRange={customDateRange} />

            <div className="row">
                <div className="col-lg-8">
                    <QuickActions />
                    <TrendChart />
                </div>
                <div className="col-lg-4">
                    <TodoList />
                </div>
            </div>

            {/* ── 新增：任務與品質警示區塊 ── */}
            <hr className="my-4" />
            <h5 className="mb-3 text-muted">
                <i className="bi bi-exclamation-circle me-2" />
                待辦與品質警示
            </h5>
            <Row className="g-3 mb-4">
                <Col lg={6}>
                    <MyTasksWidget />
                </Col>
                <Col lg={6}>
                    <OverdueCapaWidget />
                </Col>
            </Row>
            <Row className="g-3">
                <Col lg={6}>
                    <OverdueComplaintWidget />
                </Col>
                <Col lg={6}>
                    <RecentRepeatsWidget />
                </Col>
            </Row>
        </div>
    );
};

export default DashboardPage;
