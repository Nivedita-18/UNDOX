import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('undox_token') || null);
  const [user, setUser] = useState(() => {
    try {
      const stored = localStorage.getItem('undox_user');
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  });
  const [isLoading, setIsLoading] = useState(true);

  const logout = useCallback(() => {
    localStorage.removeItem('undox_token');
    localStorage.removeItem('undox_user');
    setToken(null);
    setUser(null);
  }, []);

  // Fetch current user details on load if token exists
  useEffect(() => {
    let isMounted = true;
    async function loadUser() {
      if (!token) {
        setIsLoading(false);
        return;
      }

      try {
        const userData = await api.auth.getMe();
        if (isMounted) {
          setUser(userData);
          localStorage.setItem('undox_user', JSON.stringify(userData));
        }
      } catch (err) {
        console.warn('Failed to validate stored token, logging out', err);
        if (isMounted) {
          logout();
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadUser();

    const handleUnauthorized = () => {
      logout();
    };

    window.addEventListener('undox:unauthorized', handleUnauthorized);
    return () => {
      isMounted = false;
      window.removeEventListener('undox:unauthorized', handleUnauthorized);
    };
  }, [token, logout]);

  const login = async (username, password) => {
    setIsLoading(true);
    try {
      const data = await api.auth.login(username, password);
      localStorage.setItem('undox_token', data.access_token);
      const userProfile = {
        id: data.user_id,
        username: data.username,
        role: data.role,
      };
      localStorage.setItem('undox_user', JSON.stringify(userProfile));
      setToken(data.access_token);
      setUser(userProfile);
      return userProfile;
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (username, email, password, role = 'VIEWER') => {
    setIsLoading(true);
    try {
      await api.auth.register(username, email, password, role);
      // Automatically log in after registration
      return await login(username, password);
    } finally {
      setIsLoading(false);
    }
  };

  const isAdmin = user?.role === 'ADMIN';
  const isOperator = user?.role === 'OPERATOR' || isAdmin;
  const isViewer = user?.role === 'VIEWER';
  const canApprove = isOperator;
  const canExecute = isOperator;

  const value = {
    user,
    token,
    isAuthenticated: !!token,
    isLoading,
    login,
    register,
    logout,
    isAdmin,
    isOperator,
    isViewer,
    canApprove,
    canExecute,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
