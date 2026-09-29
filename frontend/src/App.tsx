import { Suspense, lazy } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from '@/contexts/AuthContext'
import { ThemeProvider } from '@/contexts/ThemeContext'
import Layout from '@/components/layout/Layout'
import ProtectedRoute from '@/components/auth/ProtectedRoute'
import LoadingScreen from '@/components/common/LoadingScreen'

// Lazy-loaded pages for code splitting
const LoginPage = lazy(() => import('@/pages/LoginPage'))
const DashboardPage = lazy(() => import('@/pages/DashboardPage'))
const VehiclesPage = lazy(() => import('@/pages/VehiclesPage'))
const TrajectoryPage = lazy(() => import('@/pages/TrajectoryPage'))
const GISPage = lazy(() => import('@/pages/GISPage'))
const CamerasPage = lazy(() => import('@/pages/CamerasPage'))
const CameraLivePage = lazy(() => import('@/pages/CameraLivePage'))
const AnalyticsPage = lazy(() => import('@/pages/AnalyticsPage'))
const AlertsPage = lazy(() => import('@/pages/AlertsPage'))
const AdminPage = lazy(() => import('@/pages/AdminPage'))
const RouteAnomalyPage = lazy(() => import('@/pages/RouteAnomalyPage'))
const CongestionPage = lazy(() => import('@/pages/CongestionPage'))
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage'))
const VideoDemoPage = lazy(() => import('@/pages/VideoDemoPage'))
const LiveWebcamPage = lazy(() => import('@/pages/LiveWebcamPage'))

function App() {
  return (
    <AuthProvider>
      <ThemeProvider>
        <Suspense fallback={<LoadingScreen />}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            
            <Route element={<ProtectedRoute />}>
              <Route element={<Layout />}>
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/vehicles" element={<VehiclesPage />} />
                <Route path="/trajectory" element={<TrajectoryPage />} />
                <Route path="/gis" element={<GISPage />} />
                <Route path="/cameras" element={<CamerasPage />} />
                <Route path="/cameras/:cameraId/live" element={<CameraLivePage />} />
                <Route path="/analytics" element={<AnalyticsPage />} />
                <Route path="/alerts" element={<AlertsPage />} />
                <Route path="/route-anomaly" element={<RouteAnomalyPage />} />
                <Route path="/congestion" element={<CongestionPage />} />
                <Route path="/ai-processing" element={<VideoDemoPage />} />
                <Route path="/live-webcam" element={<LiveWebcamPage />} />
                <Route path="/admin" element={<AdminPage />} />
              </Route>
            </Route>
            
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </Suspense>
      </ThemeProvider>
    </AuthProvider>
  )
}

export default App
