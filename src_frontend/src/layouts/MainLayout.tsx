import { Outlet } from 'react-router';
import { useAuth } from '../context/useAuth';
import Sidebar from '../components/Sidebar';

const MainLayout = () => {
    const { logout, user } = useAuth();

    return (
        <div className="app-wrapper">
            <Sidebar />
            
            <div className="main-wrapper">
                <header className="main-header">
                    <div className="container-fluid px-4">
                        <div className="d-flex justify-content-between align-items-center py-3">
                            <h1 className="app-title d-lg-none">
                                <i className="fa-solid fa-shield-halved me-2"></i>
                                品質小管家
                            </h1>
                            <div className="user-menu">
                                <div className="user-info">
                                    <span className="user-avatar">
                                        <i className="fa-solid fa-user"></i>
                                    </span>
                                    <span className="user-name">{user?.username}</span>
                                </div>
                                <button
                                    className="btn btn-logout"
                                    onClick={logout}
                                    data-navigation-action="logout"
                                    title="登出"
                                >
                                    <i className="fa-solid fa-right-from-bracket"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                </header>

                <main className="main-content">
                    <div className="container-fluid px-4">
                        <Outlet />
                    </div>
                </main>
            </div>
        </div>
    );
};

export default MainLayout;
