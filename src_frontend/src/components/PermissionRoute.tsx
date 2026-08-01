import type { ReactNode } from 'react';
import { Navigate } from 'react-router';

import { useAuth } from '../context/useAuth';

interface PermissionRouteProps {
  permission: string;
  children: ReactNode;
}

/** 以目前登入者的單一領域權限保護頁面內容。 */
const PermissionRoute = ({ permission, children }: PermissionRouteProps) => {
  const { isLoading, isAuthenticated, hasPermission } = useAuth();

  if (isLoading) {
    return <div role="status">載入中…</div>;
  }
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return hasPermission(permission) ? children : <Navigate to="/" replace />;
};

export default PermissionRoute;
