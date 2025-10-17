import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from './useAuth.js';

export function ProtectedRoute({ children, requiredRole = null }) {
  const { status, user, logout } = useAuth();

  // Loading state
  if (status === 'loading' || status === 'idle') {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-600">Loading...</div>
      </div>
    );
  }

  // Not authenticated - redirect to login
  if (status === 'unauthenticated') {
    return <Navigate to="/login" replace />;
  }

  // Authenticated but account pending approval - block access
  if (user?.pending_approval) {
    return (
      <div className="min-h-screen grid place-items-center bg-gray-100 p-4">
        <div className="w-[min(92vw,420px)] bg-gray-200 border border-gray-300 shadow-[0_8px_24px_rgba(0,0,0,0.08)] rounded-2xl p-6 text-center">
          <h2 className="text-2xl font-semibold mb-2">Account Pending Approval</h2>
          <p className="text-gray-700 mb-4">
            Your account is awaiting admin approval. You'll be able to access the platform once an admin reviews your request.
          </p>
          <button
            onClick={logout}
            className="px-4 py-2 rounded-lg border border-blue-600 bg-blue-600 text-white font-semibold hover:opacity-95 active:opacity-90 transition"
          >
            Logout
          </button>
        </div>
      </div>
    );
  }

  // Role-based access control
  if (requiredRole) {
    const userRole = user?.role;

    // Owner can access everything
    if (userRole === 'owner') {
      return children;
    }

    // Check if user has required role (exact match or admin can access user routes)
    const roleHierarchy = { owner: 3, admin: 2, user: 1 };
    const requiredLevel = roleHierarchy[requiredRole] || 0;
    const userLevel = roleHierarchy[userRole] || 0;

    if (userLevel < requiredLevel) {
      // Insufficient permissions - redirect to upload page
      return <Navigate to="/upload" replace />;
    }
  }

  // All checks passed - render protected content
  return children;
}