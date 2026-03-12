'use client';

import { useParams, useRouter } from 'next/navigation';
import { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import { usePortfolio, useUpdatePortfolio } from '@/hooks/use-portfolios-query';
import { useFreeze, useUnfreezePortfolio } from '@/hooks/use-freeze';
import { useDashboardSummary } from '@/hooks/use-dashboard';
import { ValueSummaryCard } from '@/components/dashboard/value-summary-card';
import { SleeveAllocationsTable } from '@/components/dashboard/sleeve-allocations-table';
import { ActivityFeed } from '@/components/dashboard/activity-feed';
import type { PortfolioUpdate } from '@/types';

export default function PortfolioDetailPage() {
  const { id } = useParams();
  const router = useRouter();
  const portfolioId = id as string;
  const { user, isLoading: authLoading } = useAuth();

  useEffect(() => {
    if (!authLoading && !user) router.push('/login');
  }, [user, authLoading, router]);

  const { data: portfolio, isLoading: portfolioLoading } = usePortfolio(portfolioId);
  const { data: dashboard, isLoading: dashboardLoading } = useDashboardSummary(portfolioId);
  const { data: freezeData } = useFreeze(portfolioId);
  const unfreezeMutation = useUnfreezePortfolio(portfolioId);
  const updatePortfolio = useUpdatePortfolio(portfolioId);

  const [isEditing, setIsEditing] = useState(false);
  const [portfolioForm, setPortfolioForm] = useState<PortfolioUpdate>({});
  const [error, setError] = useState('');

  const handlePortfolioUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      await updatePortfolio.mutateAsync(portfolioForm);
      setIsEditing(false);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(detail || 'Failed to update portfolio');
    }
  };

  if (authLoading || portfolioLoading || dashboardLoading) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-7xl mx-auto">
          <div className="animate-pulse space-y-4">
            <div className="h-32 bg-gray-200 rounded-xl"></div>
            <div className="h-64 bg-gray-200 rounded-xl"></div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div className="flex items-center gap-4">
            <button 
              onClick={() => router.push('/portfolios')}
              className="text-sm text-blue-600 hover:underline"
            >
              ← Back to Portfolios
            </button>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => router.push(`/portfolios/${portfolioId}/targets`)}
              className="px-4 py-2 bg-purple-600 text-white text-sm font-semibold rounded-lg hover:bg-purple-700 transition"
            >
              🎯 Targets
            </button>
            <button
              onClick={() => router.push(`/portfolios/${portfolioId}/ledger`)}
              className="px-4 py-2 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 transition"
            >
              📒 Ledger
            </button>
            <button
              onClick={() => router.push(`/portfolios/${portfolioId}/assistant`)}
              className="px-4 py-2 bg-emerald-600 text-white text-sm font-semibold rounded-lg hover:bg-emerald-700 transition"
            >
              🤖 Assistant
            </button>
            <button
              onClick={() => router.push(`/portfolios/${portfolioId}/market-data`)}
              className="px-4 py-2 bg-indigo-600 text-white text-sm font-semibold rounded-lg hover:bg-indigo-700 transition"
            >
              📊 Market Data
            </button>
          </div>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-50 text-red-600 rounded-xl border border-red-100">
            {error}
          </div>
        )}

        {/* Freeze Banner */}
        {freezeData?.is_frozen && (
          <div className="mb-6 p-6 bg-red-50 border-2 border-red-500 rounded-xl">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-3xl">🔒</span>
                <div>
                  <h2 className="text-xl font-bold text-red-700">PORTFOLIO FROZEN</h2>
                  <p className="text-sm text-red-600">
                    Frozen since: {freezeData.freeze?.created_at && new Date(freezeData.freeze.created_at).toLocaleString()}
                  </p>
                </div>
              </div>
              <button
                onClick={() => unfreezeMutation.mutate()}
                disabled={unfreezeMutation.isPending}
                className="px-4 py-2 bg-red-600 text-white rounded-lg font-semibold hover:bg-red-700 disabled:opacity-50"
              >
                {unfreezeMutation.isPending ? 'Unfreezing...' : 'Unfreeze Portfolio'}
              </button>
            </div>
          </div>
        )}

        {/* Portfolio Info Card */}
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 mb-8">
          <div className="flex justify-between items-start">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <h1 className="text-2xl font-bold text-gray-900">{portfolio?.name}</h1>
                <span className={`text-xs font-bold px-2 py-1 rounded ${
                  portfolio?.tax_profile === 'SIPP' ? 'bg-purple-100 text-purple-700' :
                  portfolio?.tax_profile === 'ISA' ? 'bg-green-100 text-green-700' :
                  'bg-gray-100 text-gray-700'
                }`}>
                  {portfolio?.tax_profile}
                </span>
                {portfolio?.is_enabled ? (
                  <span className="text-xs font-bold px-2 py-1 rounded bg-green-100 text-green-700">Active</span>
                ) : (
                  <span className="text-xs font-bold px-2 py-1 rounded bg-gray-100 text-gray-500">Disabled</span>
                )}
              </div>
              <div className="text-sm text-gray-500 space-y-1">
                <p><span className="font-semibold">Currency:</span> {portfolio?.base_currency}</p>
                <p><span className="font-semibold">Broker:</span> {portfolio?.broker}</p>
              </div>
            </div>
            <button
              onClick={() => {
                setPortfolioForm({});
                setIsEditing(true);
              }}
              className="px-4 py-2 text-sm font-semibold text-blue-600 border border-blue-600 rounded-lg hover:bg-blue-50 transition"
            >
              Edit Portfolio
            </button>
          </div>
        </div>

        {/* Dashboard Summary */}
        {dashboard && (
          <div className="mb-8">
            <ValueSummaryCard summary={dashboard} />
          </div>
        )}

        {/* Two Column Layout */}
        <div className="grid grid-cols-3 gap-8">
          {/* Left Column - Allocations (2/3 width) */}
          <div className="col-span-2">
            {dashboard && (
              <SleeveAllocationsTable allocations={dashboard.sleeve_allocations} />
            )}
          </div>

          {/* Right Column - Activity Feed (1/3 width) */}
          <div className="col-span-1">
            {dashboard && (
              <ActivityFeed activities={dashboard.recent_activity} />
            )}
          </div>
        </div>

        {/* Edit Modal */}
        {isEditing && portfolio && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-2xl shadow-xl max-w-md w-full">
              <div className="p-6 border-b border-gray-100">
                <h2 className="text-xl font-bold text-gray-900">Edit Portfolio</h2>
              </div>
              <form onSubmit={handlePortfolioUpdate} className="p-6 space-y-4">
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">Name</label>
                  <input
                    type="text"
                    value={portfolioForm.name || portfolio.name}
                    onChange={(e) => setPortfolioForm({ ...portfolioForm, name: e.target.value })}
                    className="w-full p-3 border rounded-xl focus:ring-2 focus:ring-blue-500 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">Broker</label>
                  <input
                    type="text"
                    value={portfolioForm.broker || portfolio.broker}
                    onChange={(e) => setPortfolioForm({ ...portfolioForm, broker: e.target.value })}
                    className="w-full p-3 border rounded-xl focus:ring-2 focus:ring-blue-500 outline-none"
                  />
                </div>
                <div className="flex gap-3 pt-4">
                  <button
                    type="button"
                    onClick={() => setIsEditing(false)}
                    className="flex-1 px-4 py-2 border border-gray-300 rounded-lg font-semibold hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={updatePortfolio.isPending}
                    className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-50"
                  >
                    {updatePortfolio.isPending ? 'Saving...' : 'Save Changes'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
