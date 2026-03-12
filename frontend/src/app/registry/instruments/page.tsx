'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import { useInstruments, useCreateInstrument, useUpdateInstrument } from '@/hooks/use-instruments';
import type { Instrument, InstrumentCreate, InstrumentUpdate, InstrumentType } from '@/types';

export default function InstrumentsPage() {
  const router = useRouter();
  const { user, isLoading: authLoading } = useAuth();

  useEffect(() => {
    if (!authLoading && !user) router.push('/login');
  }, [user, authLoading, router]);

  const [searchQuery, setSearchQuery] = useState('');
  const [isinFilter, setIsinFilter] = useState('');
  const [page, setPage] = useState(0);
  const pageSize = 25;
  
  const { data, isLoading, error, refetch } = useInstruments({
    limit: pageSize,
    offset: page * pageSize,
    q: searchQuery || undefined,
    isin: isinFilter || undefined,
  });
  
  const createInstrument = useCreateInstrument();
  const [editingInstrument, setEditingInstrument] = useState<Instrument | null>(null);
  
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [formData, setFormData] = useState<InstrumentCreate>({
    isin: '',
    name: '',
    instrument_type: 'ETF',
  });
  const [formError, setFormError] = useState('');

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');
    
    if (formData.isin.length !== 12) {
      setFormError('ISIN must be exactly 12 characters');
      return;
    }
    
    try {
      await createInstrument.mutateAsync({
        ...formData,
        isin: formData.isin.toUpperCase(),
      });
      setIsCreateModalOpen(false);
      setFormData({ isin: '', name: '', instrument_type: 'ETF' });
    } catch (err: any) {
      if (err.response?.status === 409) {
        setFormError('An instrument with this ISIN already exists');
      } else {
        const detail = err.response?.data?.detail;
        const message = Array.isArray(detail) ? detail[0]?.msg || 'Validation failed' : detail || 'Failed to create instrument';
        setFormError(message);
      }
    }
  };

  const handleEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingInstrument) return;
    
    const updateData: InstrumentUpdate = {};
    if (formData.name !== editingInstrument.name) updateData.name = formData.name;
    if (formData.instrument_type !== editingInstrument.instrument_type) {
      updateData.instrument_type = formData.instrument_type;
    }
    
    try {
      await useUpdateInstrument(editingInstrument.instrument_id).mutateAsync(updateData);
      setEditingInstrument(null);
      refetch();
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      const message = Array.isArray(detail) ? detail[0]?.msg || 'Validation failed' : detail || 'Failed to update instrument';
      setFormError(message);
    }
  };

  const openEditModal = (instrument: Instrument) => {
    setEditingInstrument(instrument);
    setFormData({
      isin: instrument.isin,
      name: instrument.name || '',
      instrument_type: instrument.instrument_type as InstrumentType,
    });
    setFormError('');
  };

  const getTypeBadgeColor = (type: string) => {
    switch (type) {
      case 'ETF': return 'bg-blue-100 text-blue-700';
      case 'STOCK': return 'bg-green-100 text-green-700';
      case 'ETC': return 'bg-yellow-100 text-yellow-700';
      case 'FUND': return 'bg-purple-100 text-purple-700';
      default: return 'bg-gray-100 text-gray-700';
    }
  };

  const totalPages = data ? Math.ceil(data.total / pageSize) : 0;

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
            <h1 className="text-3xl font-bold text-gray-900">Instrument Registry</h1>
            <button
              onClick={() => setIsCreateModalOpen(true)}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 transition shadow-md"
            >
              + Create Instrument
            </button>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex gap-1 mb-6 bg-gray-100 p-1 rounded-lg w-fit">
          <button className="px-4 py-2 bg-white rounded-md shadow-sm text-sm font-semibold text-gray-900">
            Instruments
          </button>
          <button 
            onClick={() => router.push('/registry/listings')}
            className="px-4 py-2 rounded-md text-sm font-medium text-gray-600 hover:text-gray-900"
          >
            Listings
          </button>
        </div>

        {/* Filters */}
        <div className="flex gap-4 mb-6">
          <input
            type="text"
            placeholder="Search by name..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="flex-1 max-w-md p-3 border rounded-xl focus:ring-2 focus:ring-blue-500 outline-none"
          />
          <input
            type="text"
            placeholder="Filter by ISIN..."
            value={isinFilter}
            onChange={(e) => setIsinFilter(e.target.value.toUpperCase())}
            className="w-48 p-3 border rounded-xl font-mono uppercase focus:ring-2 focus:ring-blue-500 outline-none"
          />
          {(searchQuery || isinFilter) && (
            <button
              onClick={() => { setSearchQuery(''); setIsinFilter(''); }}
              className="px-4 py-2 text-gray-600 hover:text-gray-900"
            >
              Clear
            </button>
          )}
        </div>

        {/* Table */}
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
          {isLoading ? (
            <div className="p-12 text-center text-gray-500">Loading instruments...</div>
          ) : error ? (
            <div className="p-12 text-center">
              <div className="text-red-600 mb-4">Failed to load instruments</div>
              <button 
                onClick={() => refetch()}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg"
              >
                Retry
              </button>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
                <table className="w-full text-left">
                  <thead className="sticky top-0 bg-gray-50 border-b border-gray-200 z-10">
                    <tr className="text-xs uppercase tracking-wider text-gray-500 font-bold">
                      <th className="p-4">ISIN</th>
                      <th className="p-4">Name</th>
                      <th className="p-4">Type</th>
                      <th className="p-4">Created</th>
                      <th className="p-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {data?.items.map((instrument) => (
                      <tr key={instrument.instrument_id} className="hover:bg-gray-50">
                        <td className="p-4 font-mono text-sm text-gray-600">{instrument.isin}</td>
                        <td className="p-4 font-medium text-gray-900">{instrument.name || '-'}</td>
                        <td className="p-4">
                          <span className={`text-xs font-bold px-2 py-1 rounded ${getTypeBadgeColor(instrument.instrument_type)}`}>
                            {instrument.instrument_type}
                          </span>
                        </td>
                        <td className="p-4 text-sm text-gray-500">
                          {new Date(instrument.created_at).toLocaleDateString()}
                        </td>
                        <td className="p-4 text-right">
                          <button
                            onClick={() => openEditModal(instrument)}
                            className="text-sm text-blue-600 hover:text-blue-800 font-semibold"
                          >
                            Edit
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              <div className="flex justify-between items-center p-4 border-t bg-gray-50 text-sm">
                <div className="text-gray-600">
                  Showing {data && data.items.length > 0 ? page * pageSize + 1 : 0} - 
                  {data ? Math.min((page + 1) * pageSize, data.total) : 0} of {data?.total || 0} instruments
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
          <div className="bg-white rounded-2xl p-8 w-full max-w-md shadow-xl">
            <h2 className="text-2xl font-bold text-gray-900 mb-6">Create Instrument</h2>
            {formError && (
              <div className="mb-4 p-3 bg-red-50 text-red-600 text-sm rounded-lg">{formError}</div>
            )}
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">ISIN * (12 characters)</label>
                <input
                  type="text"
                  maxLength={12}
                  value={formData.isin}
                  onChange={(e) => setFormData({ ...formData, isin: e.target.value.toUpperCase() })}
                  className="w-full p-3 border rounded-xl font-mono uppercase focus:ring-2 focus:ring-blue-500 outline-none"
                  placeholder="IE00BK5BQT80"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">Name *</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full p-3 border rounded-xl focus:ring-2 focus:ring-blue-500 outline-none"
                  placeholder="Vanguard FTSE All-World"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">Type *</label>
                <select
                  value={formData.instrument_type}
                  onChange={(e) => setFormData({ ...formData, instrument_type: e.target.value as InstrumentType })}
                  className="w-full p-3 border rounded-xl bg-gray-50"
                  required
                >
                  <option value="ETF">ETF</option>
                  <option value="STOCK">STOCK</option>
                  <option value="ETC">ETC</option>
                  <option value="FUND">FUND</option>
                  <option value="OTHER">OTHER</option>
                </select>
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
                  disabled={createInstrument.isPending}
                  className="flex-1 px-4 py-3 bg-blue-600 text-white rounded-xl font-semibold hover:bg-blue-700 disabled:opacity-50"
                >
                  {createInstrument.isPending ? 'Creating...' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Modal */}
      {editingInstrument && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl p-8 w-full max-w-md shadow-xl">
            <h2 className="text-2xl font-bold text-gray-900 mb-6">Edit Instrument</h2>
            {formError && (
              <div className="mb-4 p-3 bg-red-50 text-red-600 text-sm rounded-lg">{formError}</div>
            )}
            <form onSubmit={handleEdit} className="space-y-4">
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">ISIN</label>
                <input
                  type="text"
                  value={formData.isin}
                  disabled
                  className="w-full p-3 border rounded-xl font-mono uppercase bg-gray-100"
                />
              </div>
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">Name</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full p-3 border rounded-xl focus:ring-2 focus:ring-blue-500 outline-none"
                />
              </div>
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">Type</label>
                <select
                  value={formData.instrument_type}
                  onChange={(e) => setFormData({ ...formData, instrument_type: e.target.value as InstrumentType })}
                  className="w-full p-3 border rounded-xl bg-gray-50"
                >
                  <option value="ETF">ETF</option>
                  <option value="STOCK">STOCK</option>
                  <option value="ETC">ETC</option>
                  <option value="FUND">FUND</option>
                  <option value="OTHER">OTHER</option>
                </select>
              </div>
              <div className="flex gap-4 pt-4">
                <button
                  type="button"
                  onClick={() => setEditingInstrument(null)}
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
