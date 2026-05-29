import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import MainLayout from './layouts/MainLayout';
import AuthLayout from './layouts/AuthLayout';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import ReworkPage from './pages/rework/ReworkPage';
import ShippingPage from './pages/shipping/ShippingPage';
import PatrolPage from './pages/patrol/PatrolPage';
import NCMRPage from './pages/ncmr/NCMRPage';
import RiskReleasePage from './pages/ncmr/RiskReleasePage';
import CAPAPage from './pages/capa/CAPAPage';
import TolerancePage from './pages/tolerance/TolerancePage';
import ExtrusionTolerancePage from './pages/extrusion-tolerance/ExtrusionTolerancePage';
import UserManagementPage from './pages/admin/UserManagementPage';
import TaskListPage from './pages/task/TaskListPage';
import ComplaintPage from './pages/complaint/ComplaintPage';
import ComplaintStatsPage from './pages/complaint/ComplaintStatsPage';
import VendorPerformancePage from './pages/vendor/VendorPerformancePage';
import ProtectedRoute from './components/ProtectedRoute';
import AdminRoute from './components/AdminRoute';

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* 公開路由 (登入頁) */}
          <Route element={<AuthLayout />}>
            <Route path="/login" element={<LoginPage />} />
          </Route>

          {/* 受保護路由 */}
          <Route element={<ProtectedRoute />}>
            <Route element={<MainLayout />}>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/rework" element={<ReworkPage />} />
              <Route path="/shipping" element={<ShippingPage />} /> {/* Added ShippingPage route */}
              <Route path="/patrol" element={<PatrolPage />} /> {/* Added PatrolPage route */}
              <Route path="/ncmr" element={<NCMRPage />} /> {/* Added NCMRPage route */}
              <Route path="/ncmr/risk-releases" element={<RiskReleasePage />} /> {/* 未授權放行風險清單 */}
              <Route path="/capa" element={<CAPAPage />} />
              <Route path="/tasks" element={<TaskListPage />} />
              <Route path="/complaints" element={<ComplaintPage />} />
              <Route path="/complaints/stats" element={<ComplaintStatsPage />} />
              <Route path="/tolerance" element={<TolerancePage />} />
              <Route path="/extrusion-tolerance" element={<ExtrusionTolerancePage />} />
              <Route path="/vendor-performance" element={<VendorPerformancePage />} />
              {/* 未來在此處新增其他頁面路由 */}
            </Route>
          </Route>

          {/* 管理員專屬路由 */}
          <Route element={<AdminRoute />}>
            <Route element={<MainLayout />}>
              <Route path="/admin/users" element={<UserManagementPage />} />
            </Route>
          </Route>

          {/* 預設重導 */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
