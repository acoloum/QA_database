import { Navigate, Outlet } from 'react-router';
import { useAuth } from '../context/useAuth';

/** 僅允許具有 SPC 檢視權限的已登入使用者進入進階分析。 */
const SpcViewRoute = () => {
  const { isAuthenticated, isLoading, hasPermission } = useAuth();

  if (isLoading) {
    return <div className="d-flex justify-content-center align-items-center vh-100" role="status">載入中…</div>;
  }
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return hasPermission('spc.view') ? <Outlet /> : <Navigate to="/" replace />;
};

export default SpcViewRoute;
