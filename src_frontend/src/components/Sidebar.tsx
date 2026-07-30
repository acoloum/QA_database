import { NavLink } from 'react-router';
import { useState } from 'react';
import { useAuth } from '../context/useAuth';

interface MenuItem {
    title: string;
    path: string;
    icon: string;
    permission?: string;
}

interface MenuGroup {
    title?: string;
    items: MenuItem[];
    adminOnly?: boolean;
}

const Sidebar = () => {
    const [isCollapsed, setIsCollapsed] = useState(false);
    const { user, hasPermission } = useAuth();
    const isAdmin = user?.role === 'admin';

    const menuGroups: MenuGroup[] = [
        {
            items: [
                { title: '儀表板', path: '/', icon: 'fa-gauge-high' },
            ]
        },
        {
            title: '功能選單',
            items: [
                { title: '出貨檢驗', path: '/shipping', icon: 'fa-gift' },
                { title: '現場巡檢', path: '/patrol', icon: 'fa-wand-magic-sparkles' },
                { title: '不合格品', path: '/ncmr', icon: 'fa-triangle-exclamation' },
                { title: '未授權放行風險', path: '/ncmr/risk-releases', icon: 'fa-circle-exclamation' },
                { title: '重工管理', path: '/rework', icon: 'fa-rotate' },
                { title: '矯正措施', path: '/capa', icon: 'fa-file-signature' },
                { title: '客訴管理', path: '/complaints', icon: 'fa-comment-dots' },
                { title: '任務清單', path: '/tasks', icon: 'fa-list-check' },
                { title: '公差管理', path: '/tolerance', icon: 'fa-ruler-combined' },
                { title: '擠壓公差', path: '/extrusion-tolerance', icon: 'fa-compress-alt' },
                { title: '機械性質', path: '/mechanical', icon: 'fa-dumbbell' },
                { title: '廠商績效', path: '/vendor-performance', icon: 'fa-chart-line' },
                { title: '品質分析', path: '/quality-analytics', icon: 'fa-chart-simple' },
                { title: '進階 SPC', path: '/spc/advanced', icon: 'fa-chart-area', permission: 'spc.view' },
                { title: 'MSA 工作台', path: '/msa', icon: 'fa-ruler-combined', permission: 'msa.view' },
                { title: '量測設備', path: '/measurement-equipment', icon: 'fa-microscope', permission: 'calibration.view' },
                { title: '校正管理／工作佇列', path: '/calibrations', icon: 'fa-screwdriver-wrench', permission: 'calibration.view' },
            ]
        },
        {
            title: '爐溫測試 (CQI-9)',
            items: [
                { title: '爐溫總覽', path: '/pyrometry', icon: 'fa-gauge' },
                { title: '測試紀錄', path: '/pyrometry/tests', icon: 'fa-temperature-high' },
                { title: '設備主檔', path: '/pyrometry/furnaces', icon: 'fa-fire' },
                { title: '記錄器校正', path: '/pyrometry/recorders', icon: 'fa-ruler' },
                { title: '熱電偶校正', path: '/pyrometry/thermocouples', icon: 'fa-bolt' },
            ]
        },
        {
            title: '系統管理',
            adminOnly: true,
            items: [
                { title: '使用者管理', path: '/admin/users', icon: 'fa-users-gear' },
            ]
        }
    ];

    return (
        <>
            <button 
                className="sidebar-toggle d-lg-none"
                onClick={() => setIsCollapsed(!isCollapsed)}
                aria-label="切換側邊欄"
            >
                <i className={`fa-solid ${isCollapsed ? 'fa-bars' : 'fa-xmark'}`}></i>
            </button>

            {!isCollapsed && (
                <div 
                    className="sidebar-overlay d-lg-none"
                    onClick={() => setIsCollapsed(true)}
                />
            )}

            <aside className={`sidebar ${isCollapsed ? 'collapsed' : ''}`}>
                <div className="sidebar-header">
                    <div className="sidebar-logo">
                        <i className="fa-solid fa-shield-halved"></i>
                        {!isCollapsed && <span>品質小管家</span>}
                    </div>
                    <button 
                        className="sidebar-collapse-btn d-none d-lg-flex"
                        onClick={() => setIsCollapsed(!isCollapsed)}
                        title={isCollapsed ? '展開側邊欄' : '收合側邊欄'}
                    >
                        <i className={`fa-solid fa-chevron-${isCollapsed ? 'right' : 'left'}`}></i>
                    </button>
                </div>

                <nav className="sidebar-nav">
                    {menuGroups.filter(g => !g.adminOnly || isAdmin).map((group, groupIndex) => (
                        <div key={groupIndex} className="nav-group">
                            {group.title && !isCollapsed && (
                                <div className="nav-group-title">{group.title}</div>
                            )}
                            <ul className="nav-list">
                                {group.items.filter(item => !item.permission || hasPermission(item.permission)).map((item) => (
                                    <li key={item.path}>
                                        <NavLink 
                                            to={item.path}
                                            className={({ isActive }) => 
                                                `nav-link ${isActive ? 'active' : ''}`
                                            }
                                            title={isCollapsed ? item.title : undefined}
                                            onClick={() => {
                                                if (window.innerWidth < 992) {
                                                    setIsCollapsed(true);
                                                }
                                            }}
                                        >
                                            <i className={`fa-solid ${item.icon}`}></i>
                                            {!isCollapsed && <span>{item.title}</span>}
                                        </NavLink>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    ))}
                </nav>

                <div className="sidebar-footer">
                    <div className="version-info">
                        {!isCollapsed && <span>v1.0.0</span>}
                    </div>
                </div>
            </aside>
        </>
    );
};

export default Sidebar;
