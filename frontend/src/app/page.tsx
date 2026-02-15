'use client';

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import { useAuth } from '@/context/AuthContext';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

export default function Dashboard() {
  const { user, isLoading: authLoading, logout } = useAuth();
  const router = useRouter();

  // The Query Layer: Fetches portfolios and caches them under the 'portfolios' key
  const { data: portfolios, isLoading: dataLoading } = useQuery({
  queryKey: ['portfolios'],
  queryFn: async () => {
    // This matches @router.get("") in the backend
    const res = await api.get('/portfolios'); 
    return res.data;
  },
  enabled: !!user,
});

  useEffect(() => {
    if (!authLoading && !user) router.push('/login');
  }, [user, authLoading, router]);

  if (authLoading || dataLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen font-mono text-sm text-blue-600">
        Syncing with Ledger...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <header className="max-w-6xl mx-auto flex justify-between items-center mb-12">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Portfolio Dashboard</h1>
          <p className="text-sm text-gray-500 mt-1">Logged in as {user?.email}</p>
        </div>
        <div className="flex gap-4">
          <button 
            onClick={() => router.push('/registry')}
            className="px-4 py-2 text-sm font-semibold text-blue-600 border border-blue-600 rounded-lg hover:bg-blue-50 transition"
          >
            Asset Registry
          </button>
          <button 
            onClick={logout}
            className="px-4 py-2 text-sm font-semibold text-red-600 hover:bg-red-50 rounded-lg transition"
          >
            Logout
          </button>
        </div>
      </header>

      <main className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {portfolios?.map((p: any) => (
          <div 
            key={p.portfolio_id} 
            onClick={() => router.push(`/portfolios/${p.portfolio_id}`)}
            className="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm hover:shadow-md hover:border-blue-400 transition-all cursor-pointer group"
          >
            <div className="flex justify-between items-start mb-4">
              <span className="bg-gray-100 text-gray-600 text-[10px] font-bold px-2 py-1 rounded uppercase tracking-widest">
                {p.tax_profile}
              </span>
              <span className="text-gray-300 group-hover:text-blue-500 transition-colors">→</span>
            </div>
            <h2 className="text-xl font-bold text-gray-800">{p.name}</h2>
            <p className="text-sm text-gray-400 mt-1">{p.base_currency} Base</p>
            <div className="mt-6 pt-4 border-t border-gray-50 text-[10px] font-mono text-gray-300">
              REF: {p.portfolio_id}
            </div>
          </div>
        ))}
      </main>
    </div>
  );
}