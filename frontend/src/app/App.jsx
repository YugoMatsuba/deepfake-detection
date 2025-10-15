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
                  <Upload />
                </ProtectedRoute>
              }
            />
            <Route path="/upload" element={<Upload />} />
            <Route path="/analysis" element={<Analysis />}/>
            <Route path="/frame-viewer" element={<FrameViewerPage />} />
          </Routes>
        </AnalysisProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}