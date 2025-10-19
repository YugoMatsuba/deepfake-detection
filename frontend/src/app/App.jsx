import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './AuthProvider.jsx';
import { AnalysisProvider } from './AnalysisProvider.jsx';
import { ProtectedRoute } from './ProtectedRoute.jsx';
import Login from '../pages/Login.jsx';
import SignUp from '../pages/SignUp.jsx';
import Analysis from '../pages/Analysis.jsx';
import Upload from '../pages/Upload.jsx';
import FrameViewerPage from '../pages/FrameViewerRetrieval.jsx';
import RoleSelect from '../pages/RoleSelect.jsx';
import AdminDashboard from '../pages/AdminDashboard.jsx';
import Landing from '../pages/Landing.jsx';
import PastReports from '../pages/PastReports.jsx';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AnalysisProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<SignUp />} />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <Landing />
                </ProtectedRoute>
              }
            />
            <Route path="/upload" element={<Upload />} />
            <Route path="/analysis" element={<Analysis />}/>
            <Route path="/frame-viewer" element={<FrameViewerPage />} />
            <Route
              path="/reports"
              element={
                <ProtectedRoute>
                  <PastReports />
                </ProtectedRoute>
              }
            />

            {/* Admin routes - require admin role */}
            <Route
              path="/role-select"
              element={
                <ProtectedRoute requiredRole="admin">
                  <RoleSelect />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin"
              element={
                <ProtectedRoute requiredRole="admin">
                  <AdminDashboard />
                </ProtectedRoute>
              }
            />
          </Routes>
        </AnalysisProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}