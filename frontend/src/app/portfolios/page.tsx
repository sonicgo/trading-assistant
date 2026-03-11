'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { usePortfolios, useCreatePortfolio } from '@/hooks/use-portfolios-query';
import type { PortfolioCreate, TaxProfile } from '@/types';

export default function PortfoliosPage() {
  const router = useRouter();
  const { data: portfolios, isLoading, error, refetch } = usePortfolios();
  const createPortfolio = useCreatePortfolio();
  
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [formData, setFormData] = useState<PortfolioCreate>({
    name: '',
    base_currency: 'GBP',
    tax_profile: 'GIA',
    broker: 'Manual',
  });
  const [formError, setFormError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');
    
    if (!formData.name.trim()) {
      setFormError('Portfolio name is required');
      return;
    }
    
    try {
      await createPortfolio.mutateAsync(formData);
      setIsModalOpen(false);
      setFormData({ name: '', base_currency: 'GBP', tax_profile: 'GIA', broker: 'Manual' });
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      const message = Array.isArray(detail) ? detail[0]?.msg || 'Validation failed' : detail || 'Failed to create portfolio';
      setFormError(message);
    }
  };

  const getTaxProfileColor = (profile: TaxProfile) => {
    switch (profile) {
      case 'SIPP': return 'bg-purple-100 text-purple-700';
      case 'ISA': return 'bg-green-100 text-green-700';
      case 'GIA': return 'bg-gray-100 text-gray-700';
      default: return 'bg-gray-100 text-gray-700';
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-6xl mx-auto">
          <div className="animate-pulse space-y-4">
            <div className="h-8 bg-gray-200 rounded w-1/4"></div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-48 bg-gray-200 rounded-xl"></div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-6xl mx-auto text-center py-12">
          <div className="text-red-600 mb-4">Failed to load portfolios</div>
          <button 
            onClick={() => refetch()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <button 
              onClick={() => router.push('/')}
              className="text-sm text-blue-600 hover:underline mb-2"
            >
              ← Back to Dashboard
            </button>
            <h1 className="text-3xl font-bold text-gray-900">Portfolios</h1>
          </div>
          <button
            onClick={() => setIsModalOpen(true)}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 transition shadow-md"
          >
            + Create Portfolio
          </button>
        </div>

        {/* Portfolios Grid */}
        {portfolios && portfolios.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {portfolios.map((portfolio) => (
              <div
                key={portfolio.portfolio_id}
                onClick={() => router.push(`/portfolios/${portfolio.portfolio_id}`)}
                className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm hover:shadow-md hover:border-blue-400 transition-all cursor-pointer group"
              >
                <div className="flex justify-between items-start mb-4">
                  <span className={`text-[10px] font-bold px-2 py-1 rounded uppercase tracking-widest ${getTaxProfileColor(portfolio.tax_profile)}`}>
                    {portfolio.tax_profile}
                  </span>
                  <span className="text-gray-300 group-hover:text-blue-500 transition-colors">→</span>
                </div>
                <h2 className="text-xl font-bold text-gray-800 mb-2">{portfolio.name}</h2>
                <div className="text-sm text-gray-500 space-y-1">
                  <p>{portfolio.base_currency} Base Currency</p>
                  <p>Broker: {portfolio.broker}</p>
                </div>
                <div className="mt-6 pt-4 border-t border-gray-100">
                  <p className="text-[10px] font-mono text-gray-400">
                    Created {new Date(portfolio.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-12 text-center">
            <div className="text-6xl mb-4">📊</div>
            <h3 className="text-xl font-semibold text-gray-700 mb-2">No portfolios yet</h3>
            <p className="text-gray-500 mb-6">Create your first portfolio to start tracking investments</p>
            <button
              onClick={() => setIsModalOpen(true)}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 transition"
            >
              Create Portfolio
            </button>
          </div>
        )}
      </div>

      {/* Create Portfolio Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl p-8 w-full max-w-md shadow-xl">
            <h2 className="text-2xl font-bold text-gray-900 mb-6">Create Portfolio</h2>
            
            {formError && (
              <div className="mb-4 p-3 bg-red-50 text-red-600 text-sm rounded-lg">
                {formError}
              </div>
            )}
            
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  Portfolio Name *
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full p-3 border rounded-xl focus:ring-2 focus:ring-blue-500 outline-none"
                  placeholder="My Investment Portfolio"
                  required
                />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">
                    Base Currency
                  </label>
                  <select
                    value={formData.base_currency}
                    onChange={(e) => setFormData({ ...formData, base_currency: e.target.value })}
                    className="w-full p-3 border rounded-xl bg-gray-50"
                  >
                    <option value="GBP">GBP</option>
                    <option value="USD">USD</option>
                    <option value="EUR">EUR</option>
                  </select>
                </div>
                
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">
                    Tax Profile *
                  </label>
                  <select
                    value={formData.tax_profile}
                    onChange={(e) => setFormData({ ...formData, tax_profile: e.target.value as TaxProfile })}
                    className="w-full p-3 border rounded-xl bg-gray-50"
                    required
                  >
                    <option value="SIPP">SIPP</option>
                    <option value="ISA">ISA</option>
                    <option value="GIA">GIA</option>
                  </select>
                </div>
              </div>
              
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  Broker
                </label>
                <input
                  type="text"
                  value={formData.broker}
                  onChange={(e) => setFormData({ ...formData, broker: e.target.value })}
                  className="w-full p-3 border rounded-xl focus:ring-2 focus:ring-blue-500 outline-none"
                  placeholder="e.g., Interactive Brokers, Hargreaves Lansdown"
                />
              </div>
              
              <div className="flex gap-4 pt-4">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="flex-1 px-4 py-3 border border-gray-300 rounded-xl font-semibold hover:bg-gray-50 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createPortfolio.isPending}
                  className="flex-1 px-4 py-3 bg-blue-600 text-white rounded-xl font-semibold hover:bg-blue-700 transition disabled:opacity-50"
                >
                  {createPortfolio.isPending ? 'Creating...' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
