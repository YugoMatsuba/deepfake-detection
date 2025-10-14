import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../app/useAuth.js';

export default function Dashboard() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
  };

  return (
    <div className="min-h-screen bg-gray-100 p-4">
      <div className="max-w-2xl mx-auto bg-white rounded-lg shadow-md p-6">
        <div className="text-center mb-6">
          <h1 className="text-2xl font-semibold text-gray-900">Dashboard</h1>
        </div>

        <div className="mb-6">
          <p className="text-lg text-gray-700">
            Hello, <span className="font-semibold">{user?.username}</span>!
          </p>
          <p className="text-sm text-gray-500 mt-1">
            Role: {user?.role}
          </p>
        </div>

        {/* Navigation Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <button
            onClick={() => navigate('/upload')}
            className="p-6 bg-blue-50 border-2 border-blue-200 rounded-lg hover:bg-blue-100 transition text-left"
          >
            <div className="text-xl font-semibold text-blue-900 mb-2">📤 Upload Video</div>
            <p className="text-sm text-blue-700">Upload a video for deepfake analysis</p>
          </button>

          <button
            onClick={() => navigate('/analysis')}
            className="p-6 bg-green-50 border-2 border-green-200 rounded-lg hover:bg-green-100 transition text-left"
          >
            <div className="text-xl font-semibold text-green-900 mb-2">📊 View Analysis</div>
            <p className="text-sm text-green-700">View your analysis results</p>
          </button>

          <button
            onClick={() => navigate('/frame-viewer')}
            className="p-6 bg-purple-50 border-2 border-purple-200 rounded-lg hover:bg-purple-100 transition text-left"
          >
            <div className="text-xl font-semibold text-purple-900 mb-2">🎬 Frame Viewer</div>
            <p className="text-sm text-purple-700">View video frames with highlights</p>
          </button>
        </div>

        <button
          onClick={handleLogout}
          className="w-full bg-red-600 text-white py-2 px-4 rounded-lg hover:bg-red-700 transition"
        >
          Logout
        </button>
      </div>
    </div>
  );
}