import { useState } from 'react';
import WelcomeMessage from '../components/dashboard/WelcomeMessage';
import KPICards from '../components/dashboard/KPICards';
import QuickActions from '../components/dashboard/QuickActions';
import TodoList from '../components/dashboard/TodoList';
import TrendChart from '../components/dashboard/TrendChart';
import DateFilter from '../components/dashboard/DateFilter';
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
        </div>
    );
};

export default DashboardPage;
