import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import MainLayout from './layouts/MainLayout';
import AuthLayout from './layouts/AuthLayout';
import ProtectedRoute from './components/ProtectedRoute';
import AdminRoute from './components/AdminRoute';
import SpcViewRoute from './components/SpcViewRoute';

const LoginPage = lazy(() => import('./pages/LoginPage'));
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const ReworkPage = lazy(() => import('./pages/rework/ReworkPage'));
const ShippingPage = lazy(() => import('./pages/shipping/ShippingPage'));
const PatrolPage = lazy(() => import('./pages/patrol/PatrolPage'));
const NCMRPage = lazy(() => import('./pages/ncmr/NCMRPage'));
const RiskReleasePage = lazy(() => import('./pages/ncmr/RiskReleasePage'));
const CAPAPage = lazy(() => import('./pages/capa/CAPAPage'));
const TolerancePage = lazy(() => import('./pages/tolerance/TolerancePage'));
const ExtrusionTolerancePage = lazy(() => import('./pages/extrusion-tolerance/ExtrusionTolerancePage'));
const UserManagementPage = lazy(() => import('./pages/admin/UserManagementPage'));
const TaskListPage = lazy(() => import('./pages/task/TaskListPage'));
const ComplaintPage = lazy(() => import('./pages/complaint/ComplaintPage'));
const ComplaintStatsPage = lazy(() => import('./pages/complaint/ComplaintStatsPage'));
const VendorPerformancePage = lazy(() => import('./pages/vendor/VendorPerformancePage'));
const QualityAnalyticsPage = lazy(() => import('./pages/analytics/QualityAnalyticsPage'));
const FurnaceMasterPage = lazy(() => import('./pages/pyrometry/FurnaceMasterPage'));
const PyrometryTestListPage = lazy(() => import('./pages/pyrometry/PyrometryTestListPage'));
const PyrometryDashboardPage = lazy(() => import('./pages/pyrometry/PyrometryDashboardPage'));
const RecorderCalibrationPage = lazy(() => import('./pages/pyrometry/RecorderCalibrationPage'));
const ThermocoupleCalibrationPage = lazy(() => import('./pages/pyrometry/ThermocoupleCalibrationPage'));
const AdvancedSpcPage = lazy(() => import('./pages/spc/AdvancedSpcPage'));

const PageFallback = () => (
  <div className="d-flex align-items-center justify-content-center py-5 text-muted">
    載入中...
  </div>
);

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Suspense fallback={<PageFallback />}>
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
                <Route path="/shipping" element={<ShippingPage />} />
                <Route path="/patrol" element={<PatrolPage />} />
                <Route path="/ncmr" element={<NCMRPage />} />
                <Route path="/ncmr/risk-releases" element={<RiskReleasePage />} />
                <Route path="/capa" element={<CAPAPage />} />
                <Route path="/tasks" element={<TaskListPage />} />
                <Route path="/complaints" element={<ComplaintPage />} />
                <Route path="/complaints/stats" element={<ComplaintStatsPage />} />
                <Route path="/tolerance" element={<TolerancePage />} />
                <Route path="/extrusion-tolerance" element={<ExtrusionTolerancePage />} />
                <Route path="/vendor-performance" element={<VendorPerformancePage />} />
                <Route path="/quality-analytics" element={<QualityAnalyticsPage />} />
                <Route path="/pyrometry" element={<PyrometryDashboardPage />} />
                <Route path="/pyrometry/furnaces" element={<FurnaceMasterPage />} />
                <Route path="/pyrometry/tests" element={<PyrometryTestListPage />} />
                <Route path="/pyrometry/recorders" element={<RecorderCalibrationPage />} />
                <Route path="/pyrometry/thermocouples" element={<ThermocoupleCalibrationPage />} />
              </Route>
            </Route>

            <Route element={<SpcViewRoute />}>
              <Route element={<MainLayout />}>
                <Route path="/spc/advanced" element={<AdvancedSpcPage />} />
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
        </Suspense>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
