'use client';

import { useParams, useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api-client';

export default function PortfolioDetailPage() {
  const { id } = useParams();
  const router = useRouter();

  const { data: constituents, isLoading } = useQuery({
    queryKey: ['constituents', id],
    queryFn: async () => {
      const res = await api.get(`/portfolios/${id}/constituents`);
      return res.data;
    },
    enabled: !!id,
  });

  if (isLoading) return <div className="p-12 text-center font-mono animate-pulse">Loading Holdings...</div>;

  return (
    <div className="max-w-5xl mx-auto p-8">
      <button onClick={() => router.push('/')} className="text-blue-600 text-sm mb-8 hover:underline">
        ← Back to Overview
      </button>
      
      <h1 className="text-2xl font-bold mb-8">Portfolio Constituents</h1>

      <div className="bg-white rounded-2xl border shadow-sm overflow-hidden">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-gray-50 border-b text-[11px] uppercase tracking-wider text-gray-500 font-bold">
              <th className="p-4">Listing ID</th>
              <th className="p-4">Sleeve</th>
              <th className="p-4 text-center">Monitoring</th>
            </tr>
          </thead>
          <tbody className="divide-y text-sm">
            {constituents?.map((c: any) => (
              <tr key={c.listing_id} className="hover:bg-gray-50">
                <td className="p-4 font-mono text-gray-500">{c.listing_id}</td>
                <td className="p-4 font-bold text-blue-600">{c.sleeve_code}</td>
                <td className="p-4 text-center">{c.is_monitored ? '🎯' : '⏸️'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}