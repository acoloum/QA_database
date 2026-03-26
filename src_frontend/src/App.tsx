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
import CAPAPage from './pages/capa/CAPAPage';
import CARAPage from './pages/cara/CARAPage';
import TolerancePage from './pages/tolerance/TolerancePage';
import ExtrusionTolerancePage from './pages/extrusion-tolerance/ExtrusionTolerancePage';
import UserManagementPage from './pages/admin/UserManagementPage';
import ProtectedRoute from './components/ProtectedRoute';

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
              <Route path="/capa" element={<CAPAPage />} />
              <Route path="/cara" element={<CARAPage />} />
              <Route path="/tolerance" element={<TolerancePage />} />
              <Route path="/extrusion-tolerance" element={<ExtrusionTolerancePage />} />
              <Route path="/admin/users" element={<UserManagementPage />} />
              {/* 未來在此處新增其他頁面路由 */}
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
