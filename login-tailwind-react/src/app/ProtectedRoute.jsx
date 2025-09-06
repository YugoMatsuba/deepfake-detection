import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from './useAuth.js';

export function ProtectedRoute({ children }) {
  const { status } = useAuth();

  if (status === 'loading' || status === 'idle') {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-600">Loading...</div>
      </div>
    );
  }

  if (status === 'unauthenticated') {
    return <Navigate to="/login" replace />;
  }

  return children;
}