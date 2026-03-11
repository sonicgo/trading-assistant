'use client';

import { useState } from 'react';
import { useCreateLedgerBatch } from '@/hooks/use-ledger';
import { useListings } from '@/hooks/use-listings';
import type { EntryKind, LedgerEntryCreate } from '@/types';

interface LedgerEntryFormProps {
  portfolioId: string;
}

export function LedgerEntryForm({ portfolioId }: LedgerEntryFormProps) {
  const [entryKind, setEntryKind] = useState<EntryKind>('CONTRIBUTION');
  const [effectiveAt, setEffectiveAt] = useState(() => 
    new Date().toISOString().slice(0, 16)
  );
  const [listingId, setListingId] = useState('');
  const [quantity, setQuantity] = useState('');
  const [cashDelta, setCashDelta] = useState('');
  const [fee, setFee] = useState('');
  const [note, setNote] = useState('');
  const [error, setError] = useState('');

  const createBatch = useCreateLedgerBatch(portfolioId);
  const { data: listings } = useListings({ limit: 200 });

  const isHoldingEntry = entryKind === 'BUY' || entryKind === 'SELL';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    const entry: LedgerEntryCreate = {
      entry_kind: entryKind,
      effective_at: new Date(effectiveAt).toISOString(),
      net_cash_delta_gbp: cashDelta,
      note: note || undefined,
    };

    if (isHoldingEntry) {
      if (!listingId) {
        setError('Please select a listing');
        return;
      }
      entry.listing_id = listingId;
      entry.quantity_delta = quantity;
      if (fee) entry.fee_gbp = fee;
    }

    try {
      await createBatch.mutateAsync({
        entries: [entry],
      });

      setQuantity('');
      setCashDelta('');
      setFee('');
      setNote('');
      setListingId('');
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(Array.isArray(detail) ? detail[0]?.msg || detail[0] : detail || 'Failed to post entry');
    }
  };

  const getCashLabel = () => {
    switch (entryKind) {
      case 'CONTRIBUTION':
        return 'Contribution Amount (£)';
      case 'BUY':
        return 'Cash Outflow (£)';
      case 'SELL':
        return 'Cash Inflow (£)';
      default:
        return 'Cash Impact (£)';
    }
  };

  const getQuantityLabel = () => {
    switch (entryKind) {
      case 'BUY':
        return 'Quantity to Buy';
      case 'SELL':
        return 'Quantity to Sell (negative)';
      default:
        return 'Quantity';
    }
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
      <h3 className="text-lg font-bold text-gray-900 mb-4">Post New Entry</h3>

      {error && (
        <div className="mb-4 p-3 bg-red-50 text-red-600 rounded-lg text-sm">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              Entry Type
            </label>
            <select
              value={entryKind}
              onChange={(e) => setEntryKind(e.target.value as EntryKind)}
              className="w-full p-3 border rounded-xl bg-white"
            >
              <option value="CONTRIBUTION">Contribution (Top-up)</option>
              <option value="BUY">Buy</option>
              <option value="SELL">Sell</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              Effective Date
            </label>
            <input
              type="datetime-local"
              value={effectiveAt}
              onChange={(e) => setEffectiveAt(e.target.value)}
              className="w-full p-3 border rounded-xl"
              required
            />
          </div>
        </div>

        {isHoldingEntry && (
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              Listing
            </label>
            <select
              value={listingId}
              onChange={(e) => setListingId(e.target.value)}
              className="w-full p-3 border rounded-xl bg-white"
              required={isHoldingEntry}
            >
              <option value="">Select a listing...</option>
              {listings?.items.map((listing) => (
                <option key={listing.listing_id} value={listing.listing_id}>
                  {listing.ticker} ({listing.exchange})
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              {getCashLabel()}
            </label>
            <div className="relative">
              <span className="absolute left-3 top-3 text-gray-500">£</span>
              <input
                type="text"
                value={cashDelta}
                onChange={(e) => setCashDelta(e.target.value)}
                placeholder={entryKind === 'BUY' ? '-5000.00' : entryKind === 'SELL' ? '5000.00' : '1000.00'}
                className="w-full p-3 pl-7 border rounded-xl font-mono"
                required
              />
            </div>
            <p className="text-xs text-gray-500 mt-1">
              {entryKind === 'BUY' && 'Use negative for cash outflow'}
              {entryKind === 'SELL' && 'Use positive for cash inflow'}
              {entryKind === 'CONTRIBUTION' && 'Use positive for contribution'}
            </p>
          </div>

          {isHoldingEntry && (
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                {getQuantityLabel()}
              </label>
              <input
                type="text"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                placeholder={entryKind === 'SELL' ? '-100' : '100'}
                className="w-full p-3 border rounded-xl font-mono"
                required={isHoldingEntry}
              />
            </div>
          )}
        </div>

        {isHoldingEntry && (
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              Fee (£) <span className="text-gray-400 font-normal">(optional)</span>
            </label>
            <div className="relative">
              <span className="absolute left-3 top-3 text-gray-500">£</span>
              <input
                type="text"
                value={fee}
                onChange={(e) => setFee(e.target.value)}
                placeholder="0.00"
                className="w-full p-3 pl-7 border rounded-xl font-mono"
              />
            </div>
          </div>
        )}

        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            Note <span className="text-gray-400 font-normal">(optional)</span>
          </label>
          <input
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="e.g., Monthly contribution"
            className="w-full p-3 border rounded-xl"
          />
        </div>

        <div className="pt-2">
          <button
            type="submit"
            disabled={createBatch.isPending}
            className="w-full px-4 py-3 bg-blue-600 text-white rounded-xl font-semibold hover:bg-blue-700 disabled:opacity-50 transition"
          >
            {createBatch.isPending ? 'Posting...' : 'Post Entry'}
          </button>
        </div>

        <p className="text-xs text-gray-500 text-center">
          Note: Entries cannot be edited after posting. Use reversals to correct mistakes.
        </p>
      </form>
    </div>
  );
}
