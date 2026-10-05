import { useAuth } from '../../context/useAuth';
import { useDashboardStats } from '../../hooks/useDashboard';

// 中文姓名去掉單字姓氏只留名字（管隆偉 → 隆偉）；兩字以下的姓名直接顯示全名
const toGivenName = (fullName: string) => (fullName.length >= 3 ? fullName.slice(1) : fullName);

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

    const greetingName = user?.display_name
        ? toGivenName(user.display_name)
        : user?.username || '使用者';

    const pending = getTotalPending();
    const thisMonth = getTotalThisMonth();

    return (
        <div className="welcome-banner mb-4">
            <div className="welcome-content">
                <div className="welcome-text">
                    <h2 className="welcome-greeting">
                        {getGreeting()}，{greetingName}！
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
