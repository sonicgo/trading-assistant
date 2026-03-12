'use client';

import { useState } from 'react';

interface IgnoreModalProps {
  batchId: string;
  onIgnore: (reason?: string) => void;
  onClose: () => void;
  isPending: boolean;
}

export function IgnoreModal({ onIgnore, onClose, isPending }: IgnoreModalProps) {
  const [reason, setReason] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onIgnore(reason || undefined);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl max-w-md w-full">
        <div className="p-6 border-b border-gray-100">
          <h2 className="text-2xl font-bold text-gray-900">Ignore Recommendation</h2>
          <p className="text-sm text-gray-500 mt-1">
            This will mark the recommendation as ignored. No ledger entries will be created.
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="p-6 space-y-4">
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                Reason (optional)
              </label>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="e.g., Market conditions changed, will revisit next month"
                rows={3}
                className="w-full p-3 border rounded-xl resize-none focus:ring-2 focus:ring-blue-500 outline-none"
              />
            </div>
          </div>

          <div className="p-6 border-t border-gray-100 bg-gray-50 flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={isPending}
              className="px-4 py-2 border border-gray-300 rounded-lg font-semibold hover:bg-white disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isPending}
              className="px-4 py-2 bg-gray-600 text-white rounded-lg font-semibold hover:bg-gray-700 disabled:opacity-50"
            >
              {isPending ? 'Ignoring...' : 'Ignore Recommendation'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
