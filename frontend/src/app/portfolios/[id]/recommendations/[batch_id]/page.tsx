'use client';

import { useParams, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import {
  useRecommendationBatch,
  useExecuteRecommendationBatch,
  useIgnoreRecommendationBatch,
} from '@/hooks/use-recommendations';
import { ExecuteModal } from '@/components/recommendations/execute-modal';
import { IgnoreModal } from '@/components/recommendations/ignore-modal';
import type { AuditEvent } from '@/types';

// Mock function for audit events - replace with real API call when available
function useAuditEvents(portfolioId: string | undefined, entityId: string | undefined) {
  return { data: null, isLoading: false };
}

export default function RecommendationDetailPage() {
  const { id, batch_id } = useParams();
  const router = useRouter();
  const portfolioId = id as string;
  const batchId = batch_id as string;
  const { user, isLoading: authLoading } = useAuth();

  useEffect(() => {
    if (!authLoading && !user) router.push('/login');
  }, [user, authLoading, router]);

  const [showExecuteModal, setShowExecuteModal] = useState(false);
  const [showIgnoreModal, setShowIgnoreModal] = useState(false);
  const [error, setError] = useState('');

  const { data: batch, isLoading } = useRecommendationBatch(portfolioId, batchId);
  const { data: auditEvents } = useAuditEvents(portfolioId, batchId);

  const executeMutation = useExecuteRecommendationBatch(portfolioId, batchId);
  const ignoreMutation = useIgnoreRecommendationBatch(portfolioId, batchId);

  const handleExecute = async (
    lines: Array<{
      line_id: string;
      executed_quantity: string;
      executed_price_gbp: string;
      executed_fee_gbp: string;
      note?: string;
    }>
  ) => {
    setError('');
    try {
      await executeMutation.mutateAsync({ lines });
      setShowExecuteModal(false);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(detail || 'Failed to execute recommendation');
    }
  };

  const handleIgnore = async (reason?: string) => {
    setError('');
    try {
      await ignoreMutation.mutateAsync({ reason });
      setShowIgnoreModal(false);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(detail || 'Failed to ignore recommendation');
    }
  };

  const getStatusBadge = (status: string) => {
    const styles = {
      PENDING: 'bg-yellow-100 text-yellow-700',
      EXECUTED: 'bg-green-100 text-green-700',
      EXECUTED_PARTIAL: 'bg-blue-100 text-blue-700',
      IGNORED: 'bg-gray-100 text-gray-700',
    };
    return styles[status as keyof typeof styles] || 'bg-gray-100 text-gray-700';
  };

  if (authLoading || isLoading) {
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

  if (!batch) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-5xl mx-auto">
          <div className="text-center py-12">
            <h2 className="text-xl font-semibold text-gray-700">Recommendation not found</h2>
            <button
              onClick={() => router.push(`/portfolios/${portfolioId}`)}
              className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg"
            >
              Back to Portfolio
            </button>
          </div>
        </div>
      </div>
    );
  }

  const isPending = batch.status === 'PENDING';

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-5xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <button
            onClick={() => router.push(`/portfolios/${portfolioId}`)}
            className="text-sm text-blue-600 hover:underline"
          >
            ← Back to Portfolio
          </button>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-50 text-red-600 rounded-xl border border-red-100">
            {error}
          </div>
        )}

        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 mb-8">
          <div className="flex justify-between items-start">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <h1 className="text-2xl font-bold text-gray-900">Recommendation Batch</h1>
                <span className={`text-xs font-bold px-2 py-1 rounded ${getStatusBadge(batch.status)}`}>
                  {batch.status}
                </span>
              </div>
              <p className="text-sm text-gray-500">
                Generated: {new Date(batch.generated_at).toLocaleString()}
              </p>
              {batch.executed_at && (
                <p className="text-sm text-gray-500">
                  Executed: {new Date(batch.executed_at).toLocaleString()}
                </p>
              )}
              {batch.ignored_at && (
                <p className="text-sm text-gray-500">
                  Ignored: {new Date(batch.ignored_at).toLocaleString()}
                </p>
              )}
            </div>

            {isPending && (
              <div className="flex gap-3">
                <button
                  onClick={() => setShowIgnoreModal(true)}
                  className="px-4 py-2 bg-gray-600 text-white text-sm font-semibold rounded-lg hover:bg-gray-700 transition"
                >
                  Ignore
                </button>
                <button
                  onClick={() => setShowExecuteModal(true)}
                  className="px-4 py-2 bg-green-600 text-white text-sm font-semibold rounded-lg hover:bg-green-700 transition"
                >
                  Execute
                </button>
              </div>
            )}
          </div>
        </div>

        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden mb-8">
          <div className="p-6 border-b border-gray-100">
            <h2 className="text-xl font-bold text-gray-900">Trade Lines</h2>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="bg-gray-50 border-b border-gray-200 text-xs uppercase tracking-wider text-gray-500 font-bold">
                <tr>
                  <th className="p-4 text-left">Action</th>
                  <th className="p-4 text-left">Proposed</th>
                  <th className="p-4 text-left">Executed</th>
                  <th className="p-4 text-left">Status</th>
                  <th className="p-4 text-left">Note</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 text-sm">
                {batch.lines.map((line) => (
                  <tr key={line.recommendation_line_id} className="hover:bg-gray-50">
                    <td className="p-4">
                      <span
                        className={`text-xs font-bold px-2 py-1 rounded ${
                          line.action === 'BUY'
                            ? 'bg-green-100 text-green-700'
                            : 'bg-red-100 text-red-700'
                        }`}
                      >
                        {line.action}
                      </span>
                    </td>
                    <td className="p-4">
                      <div className="font-mono text-gray-900">
                        {line.proposed_quantity} @ £{line.proposed_price_gbp}
                      </div>
                      <div className="text-xs text-gray-500">
                        Value: £{line.proposed_value_gbp}
                        {parseFloat(line.proposed_fee_gbp) > 0 && ` (fee: £${line.proposed_fee_gbp})`}
                      </div>
                    </td>
                    <td className="p-4">
                      {line.executed_quantity ? (
                        <div>
                          <div className="font-mono text-gray-900">
                            {line.executed_quantity} @ £{line.executed_price_gbp}
                          </div>
                          <div className="text-xs text-gray-500">
                            Value: £{line.executed_value_gbp}
                            {line.executed_fee_gbp && parseFloat(line.executed_fee_gbp) > 0 &&
                              ` (fee: £${line.executed_fee_gbp})`}
                          </div>
                        </div>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>
                    <td className="p-4">
                      <span
                        className={`text-xs font-bold px-2 py-1 rounded ${
                          line.status === 'EXECUTED'
                            ? 'bg-green-100 text-green-700'
                            : line.status === 'IGNORED'
                            ? 'bg-gray-100 text-gray-700'
                            : 'bg-yellow-100 text-yellow-700'
                        }`}
                      >
                        {line.status}
                      </span>
                    </td>
                    <td className="p-4 text-gray-600">{line.execution_note || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {!isPending && batch.execution_summary && (
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Audit Trail</h2>
            <div className="space-y-4">
              <div className="flex items-start gap-4">
                <div className="w-2 h-2 rounded-full bg-blue-500 mt-2"></div>
                <div>
                  <p className="text-sm font-semibold text-gray-900">
                    Recommendation {batch.status === 'EXECUTED' ? 'Executed' : 'Ignored'}
                  </p>
                  <p className="text-xs text-gray-500">
                    {batch.status === 'EXECUTED' && batch.execution_summary
                      ? `Created ${String(batch.execution_summary.entries_created || 0)} ledger entries`
                      : (batch.execution_summary?.reason as string) || 'No reason provided'}
                  </p>
                  <p className="text-xs text-gray-400">
                    {new Date(
                      batch.executed_at || batch.ignored_at || batch.generated_at
                    ).toLocaleString()}
                  </p>
                </div>
              </div>

              {batch.status === 'EXECUTED' && batch.execution_summary && (
                <div className="flex items-start gap-4">
                  <div className="w-2 h-2 rounded-full bg-green-500 mt-2"></div>
                  <div>
                    <p className="text-sm font-semibold text-gray-900">Ledger Batch Created</p>
                    <p className="text-xs text-gray-500">
                      Total cash impact: £{String(batch.execution_summary.total_cash_impact || 0)}
                    </p>
                    {Boolean(batch.execution_summary?.ledger_batch_id) && (
                      <button
                        onClick={() =>
                          router.push(`/portfolios/${portfolioId}/ledger?batch=${String(batch.execution_summary?.ledger_batch_id)}`)
                        }
                        className="text-xs text-blue-600 hover:underline"
                      >
                        View in Ledger →
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {showExecuteModal && (
        <ExecuteModal
          batch={batch}
          onExecute={handleExecute}
          onClose={() => setShowExecuteModal(false)}
          isPending={executeMutation.isPending}
        />
      )}

      {showIgnoreModal && (
        <IgnoreModal
          batchId={batchId}
          onIgnore={handleIgnore}
          onClose={() => setShowIgnoreModal(false)}
          isPending={ignoreMutation.isPending}
        />
      )}
    </div>
  );
}
