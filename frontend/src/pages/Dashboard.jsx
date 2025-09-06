import React from 'react';
import { useAuth } from '../app/useAuth.js';

export default function Dashboard() {
  const { user, logout } = useAuth();

  const handleLogout = async () => {
    await logout();
  };

  return (
    <div className="min-h-screen bg-gray-100 p-4">
      <div className="max-w-md mx-auto bg-white rounded-lg shadow-md p-6">
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