'use client';

import { useTradePlan } from '@/hooks/use-engine';
import type { CurrentPosition, ProposedTrade } from '@/types';

interface TradePlanProps {
  portfolioId: string;
}

const formatCurrency = (value: string | null) => {
  if (!value) return '£0.00';
  const num = parseFloat(value);
  return `£${num.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

const formatPercentage = (value: string | null) => {
  if (!value) return '0.00%';
  const num = parseFloat(value);
  return `${num >= 0 ? '+' : ''}${num.toFixed(2)}%`;
};

export function TradePlan({ portfolioId }: TradePlanProps) {
  const { data, isLoading, error, refetch } = useTradePlan(portfolioId);

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

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-xl p-6">
        <h3 className="text-lg font-semibold text-red-700 mb-2">Error Loading Trade Plan</h3>
        <p className="text-red-600">Failed to fetch trade recommendations. Please try again.</p>
        <button
          onClick={() => refetch()}
          className="mt-4 px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-semibold hover:bg-red-700"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  if (data.is_blocked) {
    return (
      <div className="bg-red-50 border-2 border-red-500 rounded-xl p-6">
        <div className="flex items-center gap-3 mb-4">
          <span className="text-3xl">🚫</span>
          <div>
            <h2 className="text-xl font-bold text-red-700">Trading Blocked</h2>
            <p className="text-sm text-red-600">{data.block_reason}</p>
          </div>
        </div>
        <p className="text-red-700">{data.block_message}</p>
      </div>
    );
  }

  const buyTrades = data.trades.filter((t: ProposedTrade) => t.action === 'BUY');
  const sellTrades = data.trades.filter((t: ProposedTrade) => t.action === 'SELL');

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
            Total Portfolio Value
          </h3>
          <div className="text-2xl font-bold text-gray-900 font-mono tabular-nums">
            {formatCurrency(data.total_value_gbp)}
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
            Cash Balance
          </h3>
          <div className="text-2xl font-bold text-gray-900 font-mono tabular-nums">
            {formatCurrency(data.cash_balance_gbp)}
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
            Proposed Trades
          </h3>
          <div className="text-2xl font-bold text-gray-900">
            {data.trades.length}
          </div>
          <p className="text-xs text-gray-500 mt-1">
            {buyTrades.length} buys, {sellTrades.length} sells
          </p>
        </div>
      </div>

      {/* Current Allocations Table */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="p-6 border-b border-gray-100">
          <h2 className="text-xl font-bold text-gray-900">Current vs Target Allocations</h2>
          <p className="text-sm text-gray-500 mt-1">
            Assets with drift &gt; 5% are highlighted
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50 border-b border-gray-200 text-xs uppercase tracking-wider text-gray-500 font-bold">
              <tr>
                <th className="p-4 text-left">Ticker</th>
                <th className="p-4 text-right">Current Value</th>
                <th className="p-4 text-right">Target %</th>
                <th className="p-4 text-right">Current %</th>
                <th className="p-4 text-right">Drift</th>
                <th className="p-4 text-center">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.positions.map((position: CurrentPosition) => {
                const driftNum = parseFloat(position.drift_pct);
                const isDrifted = Math.abs(driftNum) > 5;
                const isOverweight = driftNum > 0;

                return (
                  <tr
                    key={position.listing_id}
                    className={isDrifted ? 'bg-amber-50' : 'hover:bg-gray-50'}
                  >
                    <td className="p-4">
                      <span className="font-mono font-bold text-gray-900">{position.ticker}</span>
                    </td>
                    <td className="p-4 text-right font-mono tabular-nums">
                      {formatCurrency(position.current_value_gbp)}
                    </td>
                    <td className="p-4 text-right font-mono tabular-nums">
                      {parseFloat(position.target_weight_pct).toFixed(2)}%
                    </td>
                    <td className="p-4 text-right font-mono tabular-nums">
                      {parseFloat(position.current_weight_pct).toFixed(2)}%
                    </td>
                    <td className="p-4 text-right">
                      <span
                        className={`font-mono tabular-nums font-semibold ${
                          isOverweight ? 'text-rose-600' : 'text-emerald-600'
                        }`}
                      >
                        {formatPercentage(position.drift_pct)}
                      </span>
                    </td>
                    <td className="p-4 text-center">
                      {isDrifted ? (
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-semibold bg-amber-100 text-amber-800">
                          ⚠️ Rebalance
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-semibold bg-green-100 text-green-800">
                          ✓ On Target
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Proposed Trades */}
      {data.trades.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="p-6 border-b border-gray-100">
            <h2 className="text-xl font-bold text-gray-900">Proposed Trades</h2>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Sells */}
              <div>
                <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
                  Sells ({sellTrades.length})
                </h3>
                <div className="space-y-3">
                  {sellTrades.length === 0 ? (
                    <p className="text-gray-400 text-sm italic">No sell orders</p>
                  ) : (
                    sellTrades.map((trade: ProposedTrade, idx: number) => (
                      <div
                        key={idx}
                        className="bg-rose-50 border border-rose-200 rounded-lg p-4"
                      >
                        <div className="flex justify-between items-start mb-2">
                          <span className="font-mono font-bold text-rose-700">{trade.ticker}</span>
                          <span className="text-xs font-semibold text-rose-600 bg-rose-100 px-2 py-1 rounded">
                            SELL
                          </span>
                        </div>
                        <div className="space-y-1 text-sm">
                          <div className="flex justify-between">
                            <span className="text-gray-600">Quantity:</span>
                            <span className="font-mono tabular-nums font-semibold">
                              {parseFloat(trade.quantity).toLocaleString()}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-600">Value:</span>
                            <span className="font-mono tabular-nums font-semibold">
                              {formatCurrency(trade.estimated_value_gbp)}
                            </span>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Buys */}
              <div>
                <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
                  Buys ({buyTrades.length})
                </h3>
                <div className="space-y-3">
                  {buyTrades.length === 0 ? (
                    <p className="text-gray-400 text-sm italic">No buy orders</p>
                  ) : (
                    buyTrades.map((trade: ProposedTrade, idx: number) => (
                      <div
                        key={idx}
                        className="bg-emerald-50 border border-emerald-200 rounded-lg p-4"
                      >
                        <div className="flex justify-between items-start mb-2">
                          <span className="font-mono font-bold text-emerald-700">{trade.ticker}</span>
                          <span className="text-xs font-semibold text-emerald-600 bg-emerald-100 px-2 py-1 rounded">
                            BUY
                          </span>
                        </div>
                        <div className="space-y-1 text-sm">
                          <div className="flex justify-between">
                            <span className="text-gray-600">Quantity:</span>
                            <span className="font-mono tabular-nums font-semibold">
                              {parseFloat(trade.quantity).toLocaleString()}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-600">Value:</span>
                            <span className="font-mono tabular-nums font-semibold">
                              {formatCurrency(trade.estimated_value_gbp)}
                            </span>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Cash Flow Summary */}
      {data.trades.length > 0 && (
        <div className="bg-gray-50 rounded-xl border border-gray-200 p-6">
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-4">
            Cash Flow Summary
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <p className="text-xs text-gray-500 mb-1">Projected Post-Trade Cash</p>
              <p className="text-xl font-bold text-gray-900 font-mono tabular-nums">
                {formatCurrency(data.projected_post_trade_cash)}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">Cash Pool Used</p>
              <p className="text-xl font-bold text-emerald-600 font-mono tabular-nums">
                {formatCurrency(data.cash_pool_used)}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">Cash Pool Remaining</p>
              <p className="text-xl font-bold text-blue-600 font-mono tabular-nums">
                {formatCurrency(data.cash_pool_remaining)}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Warnings */}
      {data.warnings.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-6">
          <h3 className="text-sm font-semibold text-amber-800 uppercase tracking-wider mb-3">
            ⚠️ Warnings
          </h3>
          <ul className="space-y-2">
            {data.warnings.map((warning: string, idx: number) => (
              <li key={idx} className="text-amber-700 text-sm">
                • {warning}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Last Updated */}
      <div className="text-right text-sm text-gray-400">
        Last updated: {new Date(data.as_of).toLocaleString('en-GB')}
        <button
          onClick={() => refetch()}
          className="ml-4 text-blue-600 hover:text-blue-800 font-semibold"
        >
          Refresh
        </button>
      </div>
    </div>
  );
}
