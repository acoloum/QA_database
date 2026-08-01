import { lazy, Suspense } from 'react';
import type { ReactNode } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router';
import { AuthProvider } from './context/AuthContext';
import { useAuth } from './context/useAuth';
import MainLayout from './layouts/MainLayout';
import AuthLayout from './layouts/AuthLayout';
import ProtectedRoute from './components/ProtectedRoute';
import AdminRoute from './components/AdminRoute';
import PermissionRoute from './components/PermissionRoute';

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
const MechanicalTestListPage = lazy(() => import('./pages/mechanical/MechanicalTestListPage'));
const MsaWorkspacePage = lazy(() => import('./pages/msa/MsaWorkspacePage'));
const MeasurementEquipmentPage = lazy(
  () => import('./pages/equipment/MeasurementEquipmentPage'),
);
const CalibrationTemplateListPage = lazy(
  () => import('./pages/calibration/CalibrationTemplateListPage'),
);
const CalibrationTemplateEditorPage = lazy(
  () => import('./pages/calibration/CalibrationTemplateEditorPage'),
);
const CalibrationEntryWizardPage = lazy(
  () => import('./pages/calibration/CalibrationEntryWizardPage'),
);
const CalibrationWorkQueuePage = lazy(
  () => import('./pages/calibration/CalibrationWorkQueuePage'),
);
const CalibrationDetailPage = lazy(
  () => import('./pages/calibration/CalibrationDetailPage'),
);
const MsaImportHistoryPage = lazy(() => import('./pages/msa/MsaImportHistoryPage'));
const MsaCriteriaPage = lazy(() => import('./pages/msa/MsaCriteriaPage'));
const MsaStudyListPage = lazy(() => import('./pages/msa/MsaStudyListPage'));
const MsaStudyWizardPage = lazy(() => import('./pages/msa/MsaStudyWizardPage'));
const MsaDataCollectionPage = lazy(
  () => import('./pages/msa/MsaDataCollectionPage'),
);

const PageFallback = () => (
  <div className="d-flex align-items-center justify-content-center py-5 text-muted">
    載入中...
  </div>
);

const CalibrationEntryRoute = ({ children }: { children: ReactNode }) => {
  const { hasPermission } = useAuth();
  return (
    hasPermission('calibration.execute')
    && hasPermission('calibration.manage')
  )
    ? children
    : <Navigate to="/measurement-equipment" replace />;
};

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
                <Route path="/rework" element={<PermissionRoute permission="rework.view"><ReworkPage /></PermissionRoute>} />
                <Route path="/shipping" element={<PermissionRoute permission="shipping.view"><ShippingPage /></PermissionRoute>} />
                <Route path="/patrol" element={<PermissionRoute permission="patrol.view"><PatrolPage /></PermissionRoute>} />
                <Route path="/ncmr" element={<PermissionRoute permission="ncmr.view"><NCMRPage /></PermissionRoute>} />
                <Route path="/ncmr/risk-releases" element={<PermissionRoute permission="ncmr.view"><RiskReleasePage /></PermissionRoute>} />
                <Route path="/capa" element={<PermissionRoute permission="capa.view"><CAPAPage /></PermissionRoute>} />
                <Route path="/tasks" element={<PermissionRoute permission="task.view"><TaskListPage /></PermissionRoute>} />
                <Route path="/complaints" element={<PermissionRoute permission="complaint.view"><ComplaintPage /></PermissionRoute>} />
                <Route path="/complaints/stats" element={<PermissionRoute permission="complaint.view"><ComplaintStatsPage /></PermissionRoute>} />
                <Route path="/tolerance" element={<PermissionRoute permission="tolerance.view"><TolerancePage /></PermissionRoute>} />
                <Route path="/extrusion-tolerance" element={<PermissionRoute permission="tolerance.view"><ExtrusionTolerancePage /></PermissionRoute>} />
                <Route path="/vendor-performance" element={<PermissionRoute permission="vendor.view"><VendorPerformancePage /></PermissionRoute>} />
                <Route path="/quality-analytics" element={<PermissionRoute permission="analytics.view"><QualityAnalyticsPage /></PermissionRoute>} />
                <Route path="/pyrometry" element={<PermissionRoute permission="pyrometry.view"><PyrometryDashboardPage /></PermissionRoute>} />
                <Route path="/pyrometry/furnaces" element={<PermissionRoute permission="pyrometry.view"><FurnaceMasterPage /></PermissionRoute>} />
                <Route path="/pyrometry/tests" element={<PermissionRoute permission="pyrometry.view"><PyrometryTestListPage /></PermissionRoute>} />
                <Route path="/pyrometry/recorders" element={<PermissionRoute permission="pyrometry.view"><RecorderCalibrationPage /></PermissionRoute>} />
                <Route path="/pyrometry/thermocouples" element={<PermissionRoute permission="pyrometry.view"><ThermocoupleCalibrationPage /></PermissionRoute>} />
                <Route path="/mechanical" element={<PermissionRoute permission="mechanical.view"><MechanicalTestListPage /></PermissionRoute>} />
                <Route path="/msa" element={<PermissionRoute permission="msa.view"><MsaWorkspacePage /></PermissionRoute>} />
                <Route path="/msa/equipment" element={<Navigate to="/measurement-equipment" replace />} />
                <Route path="/msa/imports" element={<PermissionRoute permission="msa.view"><MsaImportHistoryPage /></PermissionRoute>} />
                <Route path="/msa/criteria" element={<PermissionRoute permission="msa.view"><MsaCriteriaPage /></PermissionRoute>} />
                <Route path="/msa/studies" element={<PermissionRoute permission="msa.view"><MsaStudyListPage /></PermissionRoute>} />
                <Route path="/msa/studies/new" element={<PermissionRoute permission="msa.view"><MsaStudyWizardPage /></PermissionRoute>} />
                <Route path="/msa/studies/:studyId/edit" element={<PermissionRoute permission="msa.view"><MsaStudyWizardPage /></PermissionRoute>} />
                <Route path="/msa/studies/:studyId/collect" element={<PermissionRoute permission="msa.view"><MsaDataCollectionPage /></PermissionRoute>} />
              </Route>
            </Route>

            <Route element={<PermissionRoute permission="calibration.view"><MainLayout /></PermissionRoute>}>
                <Route path="/measurement-equipment" element={<MeasurementEquipmentPage />} />
                <Route path="/calibrations" element={<CalibrationWorkQueuePage />} />
                <Route
                  path="/calibrations/:calibrationId"
                  element={<CalibrationDetailPage />}
                />
                <Route path="/calibration/templates" element={<CalibrationTemplateListPage />} />
                <Route
                  path="/calibration/templates/:templateId"
                  element={<CalibrationTemplateEditorPage />}
                />
                <Route
                  path="/calibration/new"
                  element={(
                    <CalibrationEntryRoute>
                      <CalibrationEntryWizardPage />
                    </CalibrationEntryRoute>
                  )}
                />
                <Route
                  path="/measurement-equipment/:equipmentId/calibrations/new"
                  element={(
                    <CalibrationEntryRoute>
                      <CalibrationEntryWizardPage />
                    </CalibrationEntryRoute>
                  )}
                />
            </Route>

            <Route element={<PermissionRoute permission="spc.view"><MainLayout /></PermissionRoute>}>
                <Route path="/spc/advanced" element={<AdvancedSpcPage />} />
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
