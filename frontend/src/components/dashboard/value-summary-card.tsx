'use client';

import type { PortfolioDashboardSummary } from '@/types';

interface ValueSummaryCardProps {
  summary: PortfolioDashboardSummary;
}

export function ValueSummaryCard({ summary }: ValueSummaryCardProps) {
  const formatCurrency = (value: string) => {
    return new Intl.NumberFormat('en-GB', {
      style: 'currency',
      currency: 'GBP',
      minimumFractionDigits: 2,
    }).format(parseFloat(value));
  };

  return (
    <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6">
      <div className="flex justify-between items-start mb-6">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Portfolio Overview</h2>
          <p className="text-sm text-gray-500">
            As of {new Date(summary.as_of).toLocaleString()}
          </p>
        </div>
        {summary.is_frozen && (
          <div className="bg-red-100 text-red-700 px-3 py-1 rounded-full text-sm font-semibold flex items-center gap-2">
            <span>🔒</span> FROZEN
          </div>
        )}
        {summary.is_drifted && !summary.is_frozen && (
          <div className="bg-yellow-100 text-yellow-700 px-3 py-1 rounded-full text-sm font-semibold flex items-center gap-2">
            <span>⚠️</span> DRIFTED
          </div>
        )}
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="bg-blue-50 rounded-xl p-4">
          <p className="text-sm text-gray-600 mb-1">Total Value</p>
          <p className="text-2xl font-bold text-blue-700">
            {formatCurrency(summary.total_value_gbp)}
          </p>
        </div>
        
        <div className="bg-green-50 rounded-xl p-4">
          <p className="text-sm text-gray-600 mb-1">Cash Balance</p>
          <p className="text-2xl font-bold text-green-700">
            {formatCurrency(summary.cash_balance_gbp)}
          </p>
          <p className="text-xs text-gray-500 mt-1">
            {((parseFloat(summary.cash_balance_gbp) / parseFloat(summary.total_value_gbp)) * 100).toFixed(1)}% of portfolio
          </p>
        </div>
        
        <div className="bg-purple-50 rounded-xl p-4">
          <p className="text-sm text-gray-600 mb-1">Holdings Value</p>
          <p className="text-2xl font-bold text-purple-700">
            {formatCurrency(summary.holdings_value_gbp)}
          </p>
          <p className="text-xs text-gray-500 mt-1">
            {((parseFloat(summary.holdings_value_gbp) / parseFloat(summary.total_value_gbp)) * 100).toFixed(1)}% of portfolio
          </p>
        </div>
      </div>

      {summary.is_drifted && (
        <div className="mt-6 p-4 bg-yellow-50 border border-yellow-200 rounded-xl">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-yellow-600">⚠️</span>
            <span className="font-semibold text-yellow-800">Portfolio Drift Alert</span>
          </div>
          <p className="text-sm text-yellow-700">
            Maximum drift is {parseFloat(summary.max_drift_pct).toFixed(2)}%, exceeding the {summary.drift_threshold_pct}% threshold. 
            Consider rebalancing through the Assistant.
          </p>
        </div>
      )}
    </div>
  );
}
