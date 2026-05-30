import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/useAuth';

/** AdminRoute — 允許 admin 或具備 user.manage 權限的使用者存取 */
const AdminRoute = () => {
    const { isAuthenticated, isLoading, user } = useAuth();

    if (isLoading) {
        return (
            <div className="d-flex justify-content-center align-items-center vh-100">
                <div className="spinner-border text-primary" role="status">
                    <span className="visually-hidden">Loading...</span>
                </div>
            </div>
        );
    }

    if (!isAuthenticated) return <Navigate to="/login" replace />;
    const canManageUsers = user?.role === 'admin' || user?.permissions?.['user.manage'];
    if (!canManageUsers) return <Navigate to="/" replace />;

    return <Outlet />;
};

export default AdminRoute;
