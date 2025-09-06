import React, { createContext, useContext, useState, useEffect } from 'react';
import { apiLogin, apiMe, apiLogout } from '../api/auth.js';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState('idle'); // 'idle' | 'loading' | 'authenticated' | 'unauthenticated'
  const [error, setError] = useState(null);

  // Check authentication on mount
  useEffect(() => {
    refreshMe();
  }, []);

  const refreshMe = async () => {
    setStatus('loading');
    setError(null);
    
    try {
      const data = await apiMe();
      setUser(data.user);
      setStatus('authenticated');
    } catch (err) {
      setUser(null);
      if (err.status === 401) {
        // Not authenticated
        setStatus('unauthenticated');
      } else if (err.status === 0) {
        // Backend unavailable
        setStatus('unauthenticated');
        setError('backend_unavailable');
      } else {
        setStatus('unauthenticated');
        setError(err.message);
      }
    }
  };

  const login = async (username, password) => {
    setError(null);
    
    try {
      const data = await apiLogin({ username, password });
      setUser(data.user);
      setStatus('authenticated');
      return data;
    } catch (err) {
      // Let the caller handle the error
      throw err;
    }
  };

  const logout = async () => {
    try {
      await apiLogout();
    } catch {
      // Ignore logout errors
    }
    
    setUser(null);
    setStatus('unauthenticated');
    setError(null);
  };

  const value = {
    user,
    status,
    error,
    login,
    logout,
    refreshMe
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}