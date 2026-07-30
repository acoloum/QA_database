import { Navigate, Outlet } from 'react-router';

import { useAuth } from '../context/useAuth';

export default function CalibrationViewRoute() {
  const { isAuthenticated, isLoading, hasPermission } = useAuth();

  if (isLoading) {
    return (
      <div
        className="d-flex justify-content-center align-items-center vh-100"
        role="status"
      >
        載入中…
      </div>
    );
  }
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return hasPermission('calibration.view')
    ? <Outlet />
    : <Navigate to="/" replace />;
}
