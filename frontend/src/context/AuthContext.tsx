'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import { api } from '@/lib/api-client';

interface AuthContextType {
  user: any | null;
  isLoading: boolean;
  login: (credentials: { email: string; password: string }) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    api.get('/auth/me')
      .then(res => setUser(res.data))
      .catch(() => setUser(null))
      .finally(() => setIsLoading(false));
  }, []);

  const login = async (credentials: { email: string; password: string }) => {
    try {
      const response = await api.post('/auth/login', credentials);

      // Extract the access token from the response body
      const { access_token } = response.data;

      // Attach it to all FUTURE requests from the 'api' instance
      api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;

      // Now this call will succeed because the header is present
      const res = await api.get('/auth/me');
      setUser(res.data);
    } catch (error: any) {
      console.error("Login Error:", error.response?.data || error.message);
      throw error;
    }
  };

  const logout = async () => {
    await api.post('/auth/logout');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
};
