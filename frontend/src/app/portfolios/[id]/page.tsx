'use client';

import { useParams, useRouter } from 'next/navigation';
import { useState, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { usePortfolio, useUpdatePortfolio } from '@/hooks/use-portfolios-query';
import { useConstituents, useBulkUpsertConstituents } from '@/hooks/use-constituents';
import { useListings } from '@/hooks/use-listings';
import { useSleeves } from '@/hooks/use-sleeves';
import type { PortfolioUpdate, ConstituentItem } from '@/types';

export default function PortfolioDetailPage() {
  const { id } = useParams();
  const router = useRouter();
  const portfolioId = id as string;
  const queryClient = useQueryClient();

  const { data: portfolio, isLoading: portfolioLoading } = usePortfolio(portfolioId);
  const { data: constituents, isLoading: constituentsLoading } = useConstituents(portfolioId);
  const { data: sleeves } = useSleeves();
  const { data: listings } = useListings({ limit: 200 });
  const updatePortfolio = useUpdatePortfolio(portfolioId);
  const bulkUpsert = useBulkUpsertConstituents(portfolioId);

  const [isEditingPortfolio, setIsEditingPortfolio] = useState(false);
  const [portfolioForm, setPortfolioForm] = useState<PortfolioUpdate>({});
  const [isEditingConstituents, setIsEditingConstituents] = useState(false);
  const [editingItems, setEditingItems] = useState<ConstituentItem[]>([]);
  const [selectedListingId, setSelectedListingId] = useState('');
  const [selectedSleeveCode, setSelectedSleeveCode] = useState('');
  const [isMonitored, setIsMonitored] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (constituents && !isEditingConstituents) {
      setEditingItems(constituents.map(c => ({
        listing_id: c.listing_id,
        sleeve_code: c.sleeve_code,
        is_monitored: c.is_monitored,
      })));
    }
  }, [constituents, isEditingConstituents]);

  const handlePortfolioUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      await updatePortfolio.mutateAsync(portfolioForm);
      setIsEditingPortfolio(false);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      const message = Array.isArray(detail) ? detail[0]?.msg || 'Validation failed' : detail || 'Failed to update portfolio';
      setError(message);
    }
  };

  const addConstituent = () => {
    if (!selectedListingId || !selectedSleeveCode) {
      setError('Please select both a listing and sleeve');
      return;
    }
    
    const exists = editingItems.some(item => item.listing_id === selectedListingId);
    if (exists) {
      setError('This listing is already in the portfolio');
      return;
    }

    setEditingItems([...editingItems, {
      listing_id: selectedListingId,
      sleeve_code: selectedSleeveCode,
      is_monitored: isMonitored,
    }]);
    
    setSelectedListingId('');
    setSelectedSleeveCode('');
    setIsMonitored(true);
    setError('');
  };

  const removeConstituent = (listingId: string) => {
    setEditingItems(editingItems.filter(item => item.listing_id !== listingId));
  };

  const updateConstituentSleeve = (listingId: string, sleeveCode: string) => {
    setEditingItems(editingItems.map(item => 
      item.listing_id === listingId ? { ...item, sleeve_code: sleeveCode } : item
    ));
  };

  const updateConstituentMonitored = (listingId: string, monitored: boolean) => {
    setEditingItems(editingItems.map(item => 
      item.listing_id === listingId ? { ...item, is_monitored: monitored } : item
    ));
  };

  const handleSaveConstituents = async () => {
    setError('');
    try {
      await bulkUpsert.mutateAsync(editingItems);
      setIsEditingConstituents(false);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      const message = Array.isArray(detail) ? detail[0]?.msg || 'Validation failed' : detail || 'Failed to save constituents';
      setError(message);
    }
  };

  const getListingDetails = (listingId: string) => {
    return listings?.items.find(l => l.listing_id === listingId);
  };

  const getSleeveName = (sleeveCode: string) => {
    return sleeves?.find(s => s.sleeve_code === sleeveCode)?.name || sleeveCode;
  };

  if (portfolioLoading || constituentsLoading) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-5xl mx-auto">
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
      <div className="max-w-5xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <button 
            onClick={() => router.push('/portfolios')}
            className="text-sm text-blue-600 hover:underline"
          >
            ← Back to Portfolios
          </button>
          <div className="flex gap-3">
            <button
              onClick={() => router.push('/')}
              className="text-sm text-gray-600 hover:text-gray-900"
            >
              Dashboard
            </button>
          </div>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-50 text-red-600 rounded-xl border border-red-100">
            {error}
          </div>
        )}

        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 mb-8">
          {isEditingPortfolio ? (
            <form onSubmit={handlePortfolioUpdate} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">Name</label>
                  <input
                    type="text"
                    value={portfolioForm.name || portfolio?.name}
                    onChange={(e) => setPortfolioForm({ ...portfolioForm, name: e.target.value })}
                    className="w-full p-3 border rounded-xl focus:ring-2 focus:ring-blue-500 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">Broker</label>
                  <input
                    type="text"
                    value={portfolioForm.broker || portfolio?.broker}
                    onChange={(e) => setPortfolioForm({ ...portfolioForm, broker: e.target.value })}
                    className="w-full p-3 border rounded-xl focus:ring-2 focus:ring-blue-500 outline-none"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">Base Currency</label>
                  <select
                    value={portfolioForm.base_currency || portfolio?.base_currency}
                    onChange={(e) => setPortfolioForm({ ...portfolioForm, base_currency: e.target.value })}
                    className="w-full p-3 border rounded-xl bg-gray-50"
                  >
                    <option value="GBP">GBP</option>
                    <option value="USD">USD</option>
                    <option value="EUR">EUR</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">Tax Profile</label>
                  <select
                    value={portfolioForm.tax_profile || portfolio?.tax_profile}
                    onChange={(e) => setPortfolioForm({ ...portfolioForm, tax_profile: e.target.value as any })}
                    className="w-full p-3 border rounded-xl bg-gray-50"
                  >
                    <option value="SIPP">SIPP</option>
                    <option value="ISA">ISA</option>
                    <option value="GIA">GIA</option>
                  </select>
                </div>
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setIsEditingPortfolio(false)}
                  className="px-4 py-2 border border-gray-300 rounded-lg font-semibold hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={updatePortfolio.isPending}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-50"
                >
                  {updatePortfolio.isPending ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </form>
          ) : (
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
                  <p><span className="font-semibold">Created:</span> {portfolio && new Date(portfolio.created_at).toLocaleDateString()}</p>
                </div>
              </div>
              <button
                onClick={() => {
                  setPortfolioForm({});
                  setIsEditingPortfolio(true);
                }}
                className="px-4 py-2 text-sm font-semibold text-blue-600 border border-blue-600 rounded-lg hover:bg-blue-50 transition"
              >
                Edit Portfolio
              </button>
            </div>
          )}
        </div>

        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="p-6 border-b border-gray-100 flex justify-between items-center">
            <div>
              <h2 className="text-xl font-bold text-gray-900">Constituents</h2>
              <p className="text-sm text-gray-500 mt-1">
                {constituents?.length || 0} holdings mapped to sleeves
              </p>
            </div>
            <div className="flex gap-3">
              {isEditingConstituents ? (
                <>
                  <button
                    onClick={() => {
                      setIsEditingConstituents(false);
                      setEditingItems(constituents?.map(c => ({
                        listing_id: c.listing_id,
                        sleeve_code: c.sleeve_code,
                        is_monitored: c.is_monitored,
                      })) || []);
                    }}
                    className="px-4 py-2 border border-gray-300 rounded-lg font-semibold hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSaveConstituents}
                    disabled={bulkUpsert.isPending}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-50"
                  >
                    {bulkUpsert.isPending ? 'Saving...' : 'Save All Changes'}
                  </button>
                </>
              ) : (
                <button
                  onClick={() => setIsEditingConstituents(true)}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 transition"
                >
                  Edit Constituents
                </button>
              )}
            </div>
          </div>

          {isEditingConstituents && (
            <div className="p-4 bg-gray-50 border-b border-gray-100">
              <div className="flex flex-wrap gap-3 items-end">
                <div className="flex-1 min-w-[200px]">
                  <label className="block text-xs font-semibold text-gray-600 mb-1">Listing</label>
                  <select
                    value={selectedListingId}
                    onChange={(e) => setSelectedListingId(e.target.value)}
                    className="w-full p-2 border rounded-lg bg-white text-sm"
                  >
                    <option value="">Select listing...</option>
                    {listings?.items.map((listing) => (
                      <option key={listing.listing_id} value={listing.listing_id}>
                        {listing.ticker} ({listing.exchange}) - {listing.trading_currency}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="w-40">
                  <label className="block text-xs font-semibold text-gray-600 mb-1">Sleeve</label>
                  <select
                    value={selectedSleeveCode}
                    onChange={(e) => setSelectedSleeveCode(e.target.value)}
                    className="w-full p-2 border rounded-lg bg-white text-sm"
                  >
                    <option value="">Select...</option>
                    {sleeves?.map((sleeve) => (
                      <option key={sleeve.sleeve_code} value={sleeve.sleeve_code}>
                        {sleeve.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex items-center gap-2 pb-2">
                  <input
                    type="checkbox"
                    id="is_monitored"
                    checked={isMonitored}
                    onChange={(e) => setIsMonitored(e.target.checked)}
                    className="w-4 h-4"
                  />
                  <label htmlFor="is_monitored" className="text-sm font-semibold text-gray-700">Monitored</label>
                </div>
                <button
                  onClick={addConstituent}
                  className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-semibold hover:bg-green-700"
                >
                  Add
                </button>
              </div>
            </div>
          )}

          <table className="w-full text-left">
            <thead className="bg-gray-50 border-b text-xs uppercase tracking-wider text-gray-500 font-bold">
              <tr>
                <th className="p-4">Listing</th>
                <th className="p-4">Sleeve</th>
                <th className="p-4 text-center">Monitored</th>
                {isEditingConstituents && <th className="p-4 text-right">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 text-sm">
              {editingItems.length > 0 ? (
                editingItems.map((item) => {
                  const listing = getListingDetails(item.listing_id);
                  return (
                    <tr key={item.listing_id} className="hover:bg-gray-50">
                      <td className="p-4">
                        <div className="font-mono font-bold text-gray-900">{listing?.ticker || 'Unknown'}</div>
                        <div className="text-xs text-gray-500">
                          {listing?.exchange} • {listing?.trading_currency}
                          {listing?.price_scale === 'MINOR' && listing?.trading_currency === 'GBP' && ' (GBX)'}
                        </div>
                      </td>
                      <td className="p-4">
                        {isEditingConstituents ? (
                          <select
                            value={item.sleeve_code}
                            onChange={(e) => updateConstituentSleeve(item.listing_id, e.target.value)}
                            className="p-2 border rounded-lg bg-white text-sm"
                          >
                            {sleeves?.map((sleeve) => (
                              <option key={sleeve.sleeve_code} value={sleeve.sleeve_code}>
                                {sleeve.name}
                              </option>
                            ))}
                          </select>
                        ) : (
                          <span className="font-semibold text-blue-600">{getSleeveName(item.sleeve_code)}</span>
                        )}
                      </td>
                      <td className="p-4 text-center">
                        {isEditingConstituents ? (
                          <input
                            type="checkbox"
                            checked={item.is_monitored}
                            onChange={(e) => updateConstituentMonitored(item.listing_id, e.target.checked)}
                            className="w-4 h-4"
                          />
                        ) : (
                          item.is_monitored ? <span className="text-green-600 text-lg">✓</span> : <span className="text-gray-300 text-lg">-</span>
                        )}
                      </td>
                      {isEditingConstituents && (
                        <td className="p-4 text-right">
                          <button
                            onClick={() => removeConstituent(item.listing_id)}
                            className="text-sm text-red-600 hover:text-red-800 font-semibold"
                          >
                            Remove
                          </button>
                        </td>
                      )}
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={isEditingConstituents ? 4 : 3} className="p-8 text-center text-gray-500">
                    {isEditingConstituents 
                      ? 'Add constituents above to build your portfolio'
                      : 'No constituents yet. Click "Edit Constituents" to add holdings.'
                    }
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
