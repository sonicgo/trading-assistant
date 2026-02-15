'use client';

import { useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useRouter } from 'next/navigation';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const { login } = useAuth();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    try {
      const params = new URLSearchParams();
      params.append('username', email); // FastAPI requirement
      params.append('password', password);

      await login(params);
      
      // If no error thrown, redirect
      router.push('/');
    } catch (err: any) {
      // If err.response is empty, it's likely a Network Error or CORS
      console.error("Login attempt failed:", err);
      const message = err.response?.data?.detail || "Connection refused. Is the backend running?";
      setError(message);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-100">
      <form onSubmit={handleSubmit} className="p-8 bg-white rounded-xl shadow-lg w-96 border border-gray-200">
        <h1 className="text-2xl font-bold mb-6 text-center text-gray-800">Trading Assistant</h1>
        
        {error && (
          <div className="mb-4 p-3 bg-red-50 text-red-600 text-xs rounded border border-red-100">
            {error}
          </div>
        )}

        <div className="space-y-4">
          <input
            type="email"
            placeholder="Email"
            className="w-full p-3 border rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <input
            type="password"
            placeholder="Password"
            className="w-full p-3 border rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <button type="submit" className="w-full py-3 bg-blue-600 text-white rounded-lg font-bold hover:bg-blue-700 transition shadow-md">
            Sign In
          </button>
        </div>
      </form>
    </div>
  );
}