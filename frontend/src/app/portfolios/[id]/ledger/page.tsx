'use client';

import { useParams, useRouter } from 'next/navigation';
import { useCashSnapshot, useHoldingSnapshots } from '@/hooks/use-snapshots';
import { useFreeze, useUnfreezePortfolio } from '@/hooks/use-freeze';
import { LedgerHistoryTable } from '@/components/ledger/ledger-history-table';
import { LedgerEntryForm } from '@/components/ledger/ledger-entry-form';
import { LedgerImportPreview } from '@/components/ledger/ledger-import-preview';

export default function LedgerPage() {
  const { id } = useParams();
  const router = useRouter();
  const portfolioId = id as string;

  const { data: cashSnapshot, isLoading: cashLoading } = useCashSnapshot(portfolioId);
  const { data: holdingsData, isLoading: holdingsLoading } = useHoldingSnapshots(portfolioId);
  const { data: freezeData } = useFreeze(portfolioId);
  const unfreezeMutation = useUnfreezePortfolio(portfolioId);

  const formatAmount = (amount: string | null | undefined) => {
    if (!amount) return '£0.00';
    const num = parseFloat(amount);
    return `£${num.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-6xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.push(`/portfolios/${portfolioId}`)}
              className="text-sm text-blue-600 hover:underline"
            >
              ← Back to Portfolio
            </button>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Ledger</h1>
        </div>

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
                  <p className="text-sm text-red-600 mt-1">
                    Ledger posting is still allowed while frozen.
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

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
              Cash Balance
            </h3>
            {cashLoading ? (
              <div className="animate-pulse h-10 bg-gray-200 rounded"></div>
            ) : (
              <div className="text-3xl font-bold text-gray-900">
                {formatAmount(cashSnapshot?.balance_gbp)}
              </div>
            )}
            <p className="text-xs text-gray-400 mt-2">
              Updated: {cashSnapshot?.updated_at ? new Date(cashSnapshot.updated_at).toLocaleString() : '-'}
            </p>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
              Holdings
            </h3>
            {holdingsLoading ? (
              <div className="animate-pulse h-10 bg-gray-200 rounded"></div>
            ) : (
              <div className="text-3xl font-bold text-gray-900">
                {holdingsData?.holdings?.length || 0}
              </div>
            )}
            <p className="text-xs text-gray-400 mt-2">
              Total Book Cost: {formatAmount(holdingsData?.total_book_cost_gbp)}
            </p>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
              Position Value
            </h3>
            <div className="text-3xl font-bold text-gray-900">
              {formatAmount(
                cashSnapshot?.balance_gbp && holdingsData?.total_book_cost_gbp
                  ? (parseFloat(cashSnapshot.balance_gbp) + parseFloat(holdingsData.total_book_cost_gbp)).toString()
                  : '0'
              )}
            </div>
            <p className="text-xs text-gray-400 mt-2">
              Cash + Holdings
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          <div className="lg:col-span-1 space-y-6">
            <LedgerEntryForm portfolioId={portfolioId} />
            <LedgerImportPreview portfolioId={portfolioId} />
          </div>

          <div className="lg:col-span-2">
            <LedgerHistoryTable portfolioId={portfolioId} />
          </div>
        </div>
      </div>
    </div>
  );
}
