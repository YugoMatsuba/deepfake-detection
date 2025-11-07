import React from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./AuthProvider.jsx";
import { AnalysisProvider } from "./AnalysisProvider.jsx";
import { ProtectedRoute } from "./ProtectedRoute.jsx";
import { ErrorBoundary } from "./ErrorBoundary.jsx";
import Login from "../pages/Login.jsx";
import SignUp from "../pages/SignUp.jsx";
import Analysis from "../pages/Analysis.jsx";
import Upload from "../pages/Upload.jsx";
import FrameViewerPage from "../pages/FrameViewerRetrieval.jsx";
import RoleSelect from "../pages/RoleSelect.jsx";
import AdminDashboard from "../pages/AdminDashboard.jsx";
import Landing from "../pages/Landing.jsx";
import PastReports from "../pages/PastReports.jsx";
import ImageAnalysis from "../pages/ImageAnalysis.jsx";

export default function App() {
  return (
    <ErrorBoundary>
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
              <Route
                path="/upload"
                element={
                  <ProtectedRoute>
                    <Upload />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/analysis"
                element={
                  <ProtectedRoute>
                    <Analysis />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/image-analysis/:id"
                element={
                  <ProtectedRoute>
                    <ImageAnalysis />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/frame-viewer"
                element={
                  <ProtectedRoute>
                    <FrameViewerPage />
                  </ProtectedRoute>
                }
              />
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
    </ErrorBoundary>
  );
}
