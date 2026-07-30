import { useNavigate } from 'react-router';

const QuickActions = () => {
    const navigate = useNavigate();

    const actions = [
        {
            label: '新增出貨',
            icon: 'fa-plus',
            path: '/shipping',
            color: '#f97316',
            bgColor: 'rgba(249, 115, 22, 0.1)'
        },
        {
            label: '新增巡檢',
            icon: 'fa-plus',
            path: '/patrol',
            color: '#8b5cf6',
            bgColor: 'rgba(139, 92, 246, 0.1)'
        },
        {
            label: '新增 NCMR',
            icon: 'fa-plus',
            path: '/ncmr',
            color: '#ef4444',
            bgColor: 'rgba(239, 68, 68, 0.1)'
        },
        {
            label: '重工申請',
            icon: 'fa-plus',
            path: '/rework',
            color: '#14b8a6',
            bgColor: 'rgba(20, 184, 166, 0.1)'
        },
        {
            label: '新增 CAR',
            icon: 'fa-plus',
            path: '/capa',
            color: '#0ea5e9',
            bgColor: 'rgba(14, 165, 233, 0.1)'
        }
    ];

    return (
        <div className="card mb-4">
            <div className="card-header d-flex align-items-center">
                <i className="fa-solid fa-bolt me-2 text-warning"></i>
                <span className="fw-bold">快速操作</span>
            </div>
            <div className="card-body py-3">
                <div className="d-flex flex-wrap gap-2">
                    {actions.map((action, index) => (
                        <button
                            key={index}
                            className="btn quick-action-btn"
                            onClick={() => navigate(action.path)}
                            style={{
                                backgroundColor: action.bgColor,
                                color: action.color,
                                border: `1px solid ${action.color}30`
                            }}
                        >
                            <i className={`fa-solid ${action.icon} me-1`}></i>
                            {action.label}
                        </button>
                    ))}
                </div>
            </div>
        </div>
    );
};

export default QuickActions;
