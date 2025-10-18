import { Navigate } from 'react-router-dom';
import { useAuth } from '../app/useAuth.js';

export default function Landing() {
  const { status, user } = useAuth();

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

  // Admin or owner - redirect to role select
  if (user?.role === 'admin' || user?.role === 'owner') {
    return <Navigate to="/role-select" replace />;
  }

  // Regular user - redirect to upload
  return <Navigate to="/upload" replace />;
}
