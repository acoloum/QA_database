import { useAuth } from '../../context/AuthContext';
import { useDashboardStats } from '../../hooks/useDashboard';

const WelcomeMessage = () => {
    const { user } = useAuth();
    const { stats } = useDashboardStats();

    const getGreeting = () => {
        const hour = new Date().getHours();
        if (hour < 12) return '早安';
        if (hour < 18) return '午安';
        return '晚安';
    };

    const getTotalPending = () => {
        if (!stats) return 0;
        return (stats.ncmr?.pending || 0) + 
               (stats.capa?.pending || 0) + 
               (stats.rework?.pending || 0);
    };

    const getTotalThisMonth = () => {
        if (!stats) return 0;
        return (stats.shipping?.current || 0) + 
               (stats.patrol?.current || 0) +
               (stats.ncmr?.current || 0) + 
               (stats.rework?.current || 0) +
               (stats.capa?.current || 0);
    };

    const pending = getTotalPending();
    const thisMonth = getTotalThisMonth();

    return (
        <div className="welcome-banner mb-4">
            <div className="welcome-content">
                <div className="welcome-text">
                    <h2 className="welcome-greeting">
                        {getGreeting()}，{user?.username || '使用者'}！
                    </h2>
                    <p className="welcome-subtitle">
                        歡迎回到品質管理系統
                    </p>
                </div>
                <div className="welcome-stats">
                    <div className="welcome-stat">
                        <span className="stat-number">{pending}</span>
                        <span className="stat-label">待處理</span>
                    </div>
                    <div className="welcome-stat-divider"></div>
                    <div className="welcome-stat">
                        <span className="stat-number">{thisMonth}</span>
                        <span className="stat-label">本月處理</span>
                    </div>
                </div>
            </div>
            <div className="welcome-decoration">
                <div className="decoration-circle circle-1"></div>
                <div className="decoration-circle circle-2"></div>
                <div className="decoration-circle circle-3"></div>
            </div>
        </div>
    );
};

export default WelcomeMessage;
