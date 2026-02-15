import { useNavigate } from 'react-router-dom';

const DashboardPage = () => {
    const navigate = useNavigate();

    const menuItems = [
        {
            title: '出貨檢驗',
            desc: '把最棒的產品交給客戶吧！',
            icon: 'fa-gift',
            bgClass: 'bg-shipping',
            path: '/shipping'
        },
        {
            title: '現場巡檢',
            desc: '巡視現場，變出完美品質！',
            icon: 'fa-wand-magic-sparkles',
            bgClass: 'bg-patrol',
            path: '/patrol'
        },
        {
            title: '不合格品',
            desc: '異常快走開！攔截不良品',
            icon: 'fa-triangle-exclamation',
            bgClass: 'bg-ncmr',
            path: '/ncmr'
        },
        {
            title: '矯正措施',
            desc: '錯誤不再犯！8D報告寫起來',
            icon: 'fa-file-signature',
            bgClass: 'bg-capa',
            path: '/capa'
        },
        {
            title: '公差管理',
            desc: '差之毫釐，失之千里',
            icon: 'fa-ruler-combined',
            bgClass: 'bg-tolerance',
            path: '/tolerance'
        },
        {
            title: '使用者管理',
            desc: '新增系統使用者',
            icon: 'fa-users-gear',
            bgClass: 'bg-admin',
            path: '/admin/users'
        },
        {
            title: 'CAR 要求',
            desc: '對供應商發出怒吼！',
            icon: 'fa-bullhorn',
            bgClass: 'bg-cara',
            path: '/cara'
        },
        {
            title: '重工管理',
            desc: '重工追蹤，品質復活',
            icon: 'fa-rotate',
            bgClass: 'bg-rework',
            path: '/rework'
        }
    ];

    return (
        <div className="row justify-content-center g-5">
            {menuItems.map((item, index) => (
                <div key={index} className="col-md-5 col-lg-4" onClick={() => navigate(item.path)}>
                    <div className={`card nav-card ${item.bgClass || ''}`}>
                        <div className="icon-bubble">
                            <i className={`fa-solid ${item.icon}`}></i>
                        </div>
                        <div className="card-body text-center">
                            <h3 className="card-title">{item.title}</h3>
                            <p className="description">{item.desc}</p>
                        </div>
                    </div>
                </div>
            ))}
        </div>
    );
};

export default DashboardPage;
