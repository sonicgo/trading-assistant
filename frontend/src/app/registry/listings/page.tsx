'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useListings, useCreateListing, useUpdateListing } from '@/hooks/use-listings';
import { useInstruments } from '@/hooks/use-instruments';
import type { Listing, ListingCreate, ListingUpdate, PriceScale } from '@/types';

export default function ListingsPage() {
  const router = useRouter();
  const [instrumentFilter, setInstrumentFilter] = useState('');
  const [exchangeFilter, setExchangeFilter] = useState('');
  const [tickerFilter, setTickerFilter] = useState('');
  const [page, setPage] = useState(0);
  const pageSize = 25;
  
  const { data, isLoading, error, refetch } = useListings({
    limit: pageSize,
    offset: page * pageSize,
    instrument_id: instrumentFilter || undefined,
    exchange: exchangeFilter || undefined,
    ticker: tickerFilter || undefined,
  });
  
  const { data: instrumentsData } = useInstruments({ limit: 200 });
  const createListing = useCreateListing();
  const [editingListing, setEditingListing] = useState<Listing | null>(null);
  
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [formData, setFormData] = useState<ListingCreate>({
    instrument_id: '',
    ticker: '',
    exchange: 'LSE',
    trading_currency: 'GBP',
    price_scale: 'MAJOR',
    is_primary: false,
  });
  const [formError, setFormError] = useState('');

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');
    
    try {
      await createListing.mutateAsync({
        ...formData,
        ticker: formData.ticker.toUpperCase(),
        exchange: formData.exchange.toUpperCase(),
      });
      setIsCreateModalOpen(false);
      setFormData({
        instrument_id: '',
        ticker: '',
        exchange: 'LSE',
        trading_currency: 'GBP',
        price_scale: 'MAJOR',
        is_primary: false,
      });
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      const message = Array.isArray(detail) ? detail[0]?.msg || 'Validation failed' : detail || 'Failed to create listing';
      setFormError(message);
    }
  };

  const handleEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingListing) return;
    
    const updateMutation = useUpdateListing(editingListing.listing_id);
    const updateData: ListingUpdate = {};
    
    if (formData.ticker !== editingListing.ticker) updateData.ticker = formData.ticker.toUpperCase();
    if (formData.exchange !== editingListing.exchange) updateData.exchange = formData.exchange.toUpperCase();
    if (formData.trading_currency !== editingListing.trading_currency) updateData.trading_currency = formData.trading_currency;
    if (formData.price_scale !== editingListing.price_scale) updateData.price_scale = formData.price_scale;
    if (formData.is_primary !== editingListing.is_primary) updateData.is_primary = formData.is_primary;
    
    try {
      await updateMutation.mutateAsync(updateData);
      setEditingListing(null);
      refetch();
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      const message = Array.isArray(detail) ? detail[0]?.msg || 'Validation failed' : detail || 'Failed to update listing';
      setFormError(message);
    }
  };

  const openEditModal = (listing: Listing) => {
    setEditingListing(listing);
    setFormData({
      instrument_id: listing.instrument_id,
      ticker: listing.ticker,
      exchange: listing.exchange,
      trading_currency: listing.trading_currency,
      price_scale: listing.price_scale,
      is_primary: listing.is_primary,
    });
    setFormError('');
  };

  const getScaleBadgeColor = (scale: PriceScale) => {
    return scale === 'MINOR' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-700';
  };

  const getCurrencyBadgeColor = (currency: string) => {
    switch (currency) {
      case 'GBP': return 'bg-purple-100 text-purple-700';
      case 'USD': return 'bg-green-100 text-green-700';
      case 'EUR': return 'bg-blue-100 text-blue-700';
      default: return 'bg-gray-100 text-gray-700';
    }
  };

  const totalPages = data ? Math.ceil(data.total / pageSize) : 0;

  const clearFilters = () => {
    setInstrumentFilter('');
    setExchangeFilter('');
    setTickerFilter('');
    setPage(0);
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <button 
            onClick={() => router.push('/')}
            className="text-sm text-blue-600 hover:underline mb-2"
          >
            ← Back to Dashboard
          </button>
          <div className="flex justify-between items-center">
            <h1 className="text-3xl font-bold text-gray-900">Listing Registry</h1>
            <button
              onClick={() => setIsCreateModalOpen(true)}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 transition shadow-md"
            >
              + Create Listing
            </button>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex gap-1 mb-6 bg-gray-100 p-1 rounded-lg w-fit">
          <button 
            onClick={() => router.push('/registry/instruments')}
            className="px-4 py-2 rounded-md text-sm font-medium text-gray-600 hover:text-gray-900"
          >
            Instruments
          </button>
          <button className="px-4 py-2 bg-white rounded-md shadow-sm text-sm font-semibold text-gray-900">
            Listings
          </button>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-4 mb-6">
          <select
            value={instrumentFilter}
            onChange={(e) => setInstrumentFilter(e.target.value)}
            className="p-3 border rounded-xl bg-gray-50 min-w-[200px]"
          >
            <option value="">All Instruments</option>
            {instrumentsData?.items.map((inst) => (
              <option key={inst.instrument_id} value={inst.instrument_id}>
                {inst.isin} - {inst.name || 'Unnamed'}
              </option>
            ))}
          </select>
          <input
            type="text"
            placeholder="Filter by exchange..."
            value={exchangeFilter}
            onChange={(e) => setExchangeFilter(e.target.value.toUpperCase())}
            className="p-3 border rounded-xl uppercase focus:ring-2 focus:ring-blue-500 outline-none w-40"
          />
          <input
            type="text"
            placeholder="Filter by ticker..."
            value={tickerFilter}
            onChange={(e) => setTickerFilter(e.target.value.toUpperCase())}
            className="p-3 border rounded-xl uppercase focus:ring-2 focus:ring-blue-500 outline-none w-40"
          />
          {(instrumentFilter || exchangeFilter || tickerFilter) && (
            <button
              onClick={clearFilters}
              className="px-4 py-2 text-gray-600 hover:text-gray-900"
            >
              Clear Filters
            </button>
          )}
        </div>

        {/* Table */}
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
          {isLoading ? (
            <div className="p-12 text-center text-gray-500">Loading listings...</div>
          ) : error ? (
            <div className="p-12 text-center">
              <div className="text-red-600 mb-4">Failed to load listings</div>
              <button 
                onClick={() => refetch()}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg"
              >
                Retry
              </button>
            </div>
          ) : (
            <>
              <table className="w-full text-left">
                <thead className="bg-gray-50 border-b">
                  <tr className="text-xs uppercase tracking-wider text-gray-500 font-bold">
                    <th className="p-4">Ticker</th>
                    <th className="p-4">Exchange</th>
                    <th className="p-4">Currency</th>
                    <th className="p-4">Price Scale</th>
                    <th className="p-4">Primary</th>
                    <th className="p-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {data?.items.map((listing) => (
                    <tr key={listing.listing_id} className="hover:bg-gray-50">
                      <td className="p-4 font-mono text-sm font-bold text-gray-900">{listing.ticker}</td>
                      <td className="p-4">
                        <span className="text-xs font-bold px-2 py-1 rounded bg-gray-100 text-gray-700">
                          {listing.exchange}
                        </span>
                      </td>
                      <td className="p-4">
                        <span className={`text-xs font-bold px-2 py-1 rounded ${getCurrencyBadgeColor(listing.trading_currency)}`}>
                          {listing.trading_currency}
                        </span>
                      </td>
                      <td className="p-4">
                        <span className={`text-xs font-bold px-2 py-1 rounded ${getScaleBadgeColor(listing.price_scale)}`}>
                          {listing.price_scale}
                          {listing.price_scale === 'MINOR' && listing.trading_currency === 'GBP' && (
                            <span className="ml-1 text-[10px]">(GBX)</span>
                          )}
                        </span>
                      </td>
                      <td className="p-4">
                        {listing.is_primary ? (
                          <span className="text-green-600 text-lg">✓</span>
                        ) : (
                          <span className="text-gray-300 text-lg">-</span>
                        )}
                      </td>
                      <td className="p-4 text-right">
                        <button
                          onClick={() => openEditModal(listing)}
                          className="text-sm text-blue-600 hover:text-blue-800 font-semibold"
                        >
                          Edit
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* Pagination */}
              <div className="flex justify-between items-center p-4 border-t bg-gray-50 text-sm">
                <div className="text-gray-600">
                  Showing {data && data.items.length > 0 ? page * pageSize + 1 : 0} - 
                  {data ? Math.min((page + 1) * pageSize, data.total) : 0} of {data?.total || 0} listings
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage(p => Math.max(0, p - 1))}
                    disabled={page === 0}
                    className="px-3 py-1 border rounded hover:bg-white disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setPage(p => p + 1)}
                    disabled={!data || page >= totalPages - 1}
                    className="px-3 py-1 border rounded hover:bg-white disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Next
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Create Modal */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl p-8 w-full max-w-md shadow-xl max-h-[90vh] overflow-y-auto">
            <h2 className="text-2xl font-bold text-gray-900 mb-6">Create Listing</h2>
            {formError && (
              <div className="mb-4 p-3 bg-red-50 text-red-600 text-sm rounded-lg">{formError}</div>
            )}
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">Instrument *</label>
                <select
                  value={formData.instrument_id}
                  onChange={(e) => setFormData({ ...formData, instrument_id: e.target.value })}
                  className="w-full p-3 border rounded-xl bg-gray-50"
                  required
                >
                  <option value="">Select instrument...</option>
                  {instrumentsData?.items.map((inst) => (
                    <option key={inst.instrument_id} value={inst.instrument_id}>
                      {inst.isin} - {inst.name || 'Unnamed'} ({inst.instrument_type})
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">Ticker *</label>
                  <input
                    type="text"
                    value={formData.ticker}
                    onChange={(e) => setFormData({ ...formData, ticker: e.target.value.toUpperCase() })}
                    className="w-full p-3 border rounded-xl font-mono uppercase focus:ring-2 focus:ring-blue-500 outline-none"
                    placeholder="VWRP"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">Exchange *</label>
                  <input
                    type="text"
                    value={formData.exchange}
                    onChange={(e) => setFormData({ ...formData, exchange: e.target.value.toUpperCase() })}
                    className="w-full p-3 border rounded-xl uppercase focus:ring-2 focus:ring-blue-500 outline-none"
                    placeholder="LSE"
                    required
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">Currency *</label>
                  <select
                    value={formData.trading_currency}
                    onChange={(e) => setFormData({ ...formData, trading_currency: e.target.value })}
                    className="w-full p-3 border rounded-xl bg-gray-50"
                    required
                  >
                    <option value="GBP">GBP</option>
                    <option value="USD">USD</option>
                    <option value="EUR">EUR</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">Price Scale *</label>
                  <select
                    value={formData.price_scale}
                    onChange={(e) => setFormData({ ...formData, price_scale: e.target.value as PriceScale })}
                    className="w-full p-3 border rounded-xl bg-gray-50"
                    required
                  >
                    <option value="MAJOR">MAJOR (whole units)</option>
                    <option value="MINOR">MINOR (pence/cents)</option>
                  </select>
                  {formData.trading_currency === 'GBP' && formData.price_scale === 'MINOR' && (
                    <p className="text-xs text-blue-600 mt-1">Will use GBX (pence)</p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-xl">
                <input
                  type="checkbox"
                  id="is_primary"
                  checked={formData.is_primary}
                  onChange={(e) => setFormData({ ...formData, is_primary: e.target.checked })}
                  className="w-4 h-4"
                />
                <label htmlFor="is_primary" className="text-sm font-semibold text-gray-700">
                  Primary Listing
                </label>
              </div>
              <div className="flex gap-4 pt-4">
                <button
                  type="button"
                  onClick={() => setIsCreateModalOpen(false)}
                  className="flex-1 px-4 py-3 border border-gray-300 rounded-xl font-semibold hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createListing.isPending}
                  className="flex-1 px-4 py-3 bg-blue-600 text-white rounded-xl font-semibold hover:bg-blue-700 disabled:opacity-50"
                >
                  {createListing.isPending ? 'Creating...' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Modal */}
      {editingListing && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl p-8 w-full max-w-md shadow-xl max-h-[90vh] overflow-y-auto">
            <h2 className="text-2xl font-bold text-gray-900 mb-6">Edit Listing</h2>
            {formError && (
              <div className="mb-4 p-3 bg-red-50 text-red-600 text-sm rounded-lg">{formError}</div>
            )}
            <form onSubmit={handleEdit} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">Ticker</label>
                  <input
                    type="text"
                    value={formData.ticker}
                    onChange={(e) => setFormData({ ...formData, ticker: e.target.value.toUpperCase() })}
                    className="w-full p-3 border rounded-xl font-mono uppercase focus:ring-2 focus:ring-blue-500 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">Exchange</label>
                  <input
                    type="text"
                    value={formData.exchange}
                    onChange={(e) => setFormData({ ...formData, exchange: e.target.value.toUpperCase() })}
                    className="w-full p-3 border rounded-xl uppercase focus:ring-2 focus:ring-blue-500 outline-none"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">Currency</label>
                  <select
                    value={formData.trading_currency}
                    onChange={(e) => setFormData({ ...formData, trading_currency: e.target.value })}
                    className="w-full p-3 border rounded-xl bg-gray-50"
                  >
                    <option value="GBP">GBP</option>
                    <option value="USD">USD</option>
                    <option value="EUR">EUR</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">Price Scale</label>
                  <select
                    value={formData.price_scale}
                    onChange={(e) => setFormData({ ...formData, price_scale: e.target.value as PriceScale })}
                    className="w-full p-3 border rounded-xl bg-gray-50"
                  >
                    <option value="MAJOR">MAJOR</option>
                    <option value="MINOR">MINOR</option>
                  </select>
                </div>
              </div>
              <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-xl">
                <input
                  type="checkbox"
                  id="edit_is_primary"
                  checked={formData.is_primary}
                  onChange={(e) => setFormData({ ...formData, is_primary: e.target.checked })}
                  className="w-4 h-4"
                />
                <label htmlFor="edit_is_primary" className="text-sm font-semibold text-gray-700">
                  Primary Listing
                </label>
              </div>
              <div className="flex gap-4 pt-4">
                <button
                  type="button"
                  onClick={() => setEditingListing(null)}
                  className="flex-1 px-4 py-3 border border-gray-300 rounded-xl font-semibold hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 px-4 py-3 bg-blue-600 text-white rounded-xl font-semibold hover:bg-blue-700"
                >
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
