import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './AuthProvider.jsx';
import { ProtectedRoute } from './ProtectedRoute.jsx';
import Login from '../pages/Login.jsx';
import Dashboard from '../pages/Dashboard.jsx';
import SignUp from '../pages/SignUp.jsx';
import Analysis from '../pages/Analysis.jsx';
import Upload from '../pages/Upload.jsx';
import FrameViewer from '../pages/FrameViewer.jsx';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<SignUp />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                {/* <Upload /> */}
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route path="/upload" element={<Upload />} />
          <Route path="/analysis" element={<Analysis />}/>
          <Route path="/frame-viewer" element={<FrameViewer videoSrc="./public/videos/rickroll.mp4"
          deepfakeFrames={[30, 75, 120, 180]}/>}/>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}