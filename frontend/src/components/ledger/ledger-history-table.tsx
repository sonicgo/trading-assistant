'use client';

import { useState } from 'react';
import { useLedgerEntries, useReverseLedgerEntries } from '@/hooks/use-ledger';
import type { LedgerEntry, EntryKind } from '@/types';

interface LedgerHistoryTableProps {
  portfolioId: string;
}

const ENTRY_KIND_LABELS: Record<EntryKind, string> = {
  CONTRIBUTION: 'Contribution',
  BUY: 'Buy',
  SELL: 'Sell',
  ADJUSTMENT: 'Adjustment',
  REVERSAL: 'Reversal',
};

const ENTRY_KIND_COLORS: Record<EntryKind, string> = {
  CONTRIBUTION: 'bg-green-100 text-green-800',
  BUY: 'bg-blue-100 text-blue-800',
  SELL: 'bg-orange-100 text-orange-800',
  ADJUSTMENT: 'bg-yellow-100 text-yellow-800',
  REVERSAL: 'bg-purple-100 text-purple-800',
};

export function LedgerHistoryTable({ portfolioId }: LedgerHistoryTableProps) {
  const [selectedEntryIds, setSelectedEntryIds] = useState<string[]>([]);
  const [reversalNote, setReversalNote] = useState('');
  const [showReversalForm, setShowReversalForm] = useState(false);
  
  const { data, isLoading } = useLedgerEntries(portfolioId, { limit: 50 });
  const reverseMutation = useReverseLedgerEntries(portfolioId);

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-8">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-200 rounded w-1/4"></div>
          <div className="h-64 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  const entries = data?.items || [];

  const handleSelectEntry = (entryId: string) => {
    setSelectedEntryIds(prev => 
      prev.includes(entryId) 
        ? prev.filter(id => id !== entryId)
        : [...prev, entryId]
    );
  };

  const handleReverse = async () => {
    if (selectedEntryIds.length === 0) return;
    
    try {
      await reverseMutation.mutateAsync({
        entry_ids: selectedEntryIds,
        note: reversalNote,
      });
      setSelectedEntryIds([]);
      setReversalNote('');
      setShowReversalForm(false);
    } catch (error) {
      console.error('Failed to reverse entries:', error);
    }
  };

  const formatAmount = (amount: string | null) => {
    if (!amount) return '-';
    const num = parseFloat(amount);
    return num.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-GB', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    });
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      <div className="p-6 border-b border-gray-100">
        <div className="flex justify-between items-start">
          <div>
            <h2 className="text-xl font-bold text-gray-900">Ledger History</h2>
            <p className="text-sm text-gray-500 mt-1">
              {data?.total || 0} entries recorded
            </p>
          </div>
          
          {selectedEntryIds.length > 0 && (
            <div className="flex items-center gap-3">
              <span className="text-sm text-gray-600">
                {selectedEntryIds.length} selected
              </span>
              {!showReversalForm ? (
                <button
                  onClick={() => setShowReversalForm(true)}
                  className="px-4 py-2 bg-purple-600 text-white rounded-lg text-sm font-semibold hover:bg-purple-700"
                >
                  Reverse Selected
                </button>
              ) : (
                <button
                  onClick={() => {
                    setShowReversalForm(false);
                    setSelectedEntryIds([]);
                  }}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-sm font-semibold hover:bg-gray-50"
                >
                  Cancel
                </button>
              )}
            </div>
          )}
        </div>

        {showReversalForm && selectedEntryIds.length > 0 && (
          <div className="mt-4 p-4 bg-purple-50 rounded-lg border border-purple-200">
            <p className="text-sm text-purple-800 mb-3">
              Create a reversal batch with compensating entries. The original entries will not be modified.
            </p>
            <div className="flex gap-3">
              <input
                type="text"
                placeholder="Optional note..."
                value={reversalNote}
                onChange={(e) => setReversalNote(e.target.value)}
                className="flex-1 px-3 py-2 border rounded-lg text-sm"
              />
              <button
                onClick={handleReverse}
                disabled={reverseMutation.isPending}
                className="px-4 py-2 bg-purple-600 text-white rounded-lg text-sm font-semibold hover:bg-purple-700 disabled:opacity-50"
              >
                {reverseMutation.isPending ? 'Reversing...' : 'Confirm Reversal'}
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
        <table className="w-full text-left text-sm">
          <thead className="sticky top-0 bg-gray-50 border-b border-gray-200 text-xs uppercase tracking-wider text-gray-500 font-bold z-10">
            <tr>
              <th className="p-4 w-10"></th>
              <th className="p-4 text-left">Type</th>
              <th className="p-4 text-left">Date</th>
              <th className="p-4 text-right">Cash Impact</th>
              <th className="p-4 text-right">Quantity</th>
              <th className="p-4 text-right">Fee</th>
              <th className="p-4 text-left">Note</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {entries.length > 0 ? (
              entries.map((entry) => (
                <tr key={entry.entry_id} className="hover:bg-gray-50">
                  <td className="p-4">
                    <input
                      type="checkbox"
                      checked={selectedEntryIds.includes(entry.entry_id)}
                      onChange={() => handleSelectEntry(entry.entry_id)}
                      className="w-4 h-4"
                    />
                  </td>
                  <td className="p-4">
                    <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-semibold ${ENTRY_KIND_COLORS[entry.entry_kind]}`}>
                      {entry.entry_kind === 'ADJUSTMENT' && (
                        <span className="mr-1">⚠️</span>
                      )}
                      {ENTRY_KIND_LABELS[entry.entry_kind]}
                    </span>
                    {entry.reversal_of_entry_id && (
                      <div className="text-xs text-gray-500 mt-1">
                        Reverses: {entry.reversal_of_entry_id.slice(0, 8)}...
                      </div>
                    )}
                  </td>
                  <td className="p-4">
                    <div className="font-medium">{formatDate(entry.effective_at)}</div>
                    <div className="text-xs text-gray-500">
                      {new Date(entry.created_at).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}
                    </div>
                  </td>
                  <td className="p-4 text-right">
                    <span className={`font-mono font-semibold tabular-nums ${
                      parseFloat(entry.net_cash_delta_gbp) >= 0 ? 'text-emerald-600' : 'text-rose-600'
                    }`}>
                      {parseFloat(entry.net_cash_delta_gbp) >= 0 ? '+' : ''}
                      £{formatAmount(entry.net_cash_delta_gbp)}
                    </span>
                  </td>
                  <td className="p-4 text-right">
                    {entry.quantity_delta ? (
                      <span className={`font-mono tabular-nums ${parseFloat(entry.quantity_delta) >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                        {parseFloat(entry.quantity_delta) >= 0 ? '+' : ''}
                        {formatAmount(entry.quantity_delta)}
                      </span>
                    ) : (
                      <span className="font-mono tabular-nums text-gray-400">-</span>
                    )}
                  </td>
                  <td className="p-4 text-right">
                    {entry.fee_gbp ? (
                      <span className="font-mono tabular-nums text-rose-600">
                        £{formatAmount(entry.fee_gbp)}
                      </span>
                    ) : (
                      <span className="font-mono tabular-nums text-gray-400">-</span>
                    )}
                  </td>
                  <td className="p-4 text-gray-600 max-w-xs truncate">
                    {entry.note || '-'}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={7} className="text-center py-12">
                  <div className="text-4xl mb-3">📊</div>
                  <p className="text-gray-500 font-medium">No ledger entries yet</p>
                  <p className="text-gray-400 text-sm mt-1">Use the form above to post your first transaction</p>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
