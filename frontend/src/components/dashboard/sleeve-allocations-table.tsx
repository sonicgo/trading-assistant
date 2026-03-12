'use client';

import type { SleeveAllocation } from '@/types';

interface SleeveAllocationsTableProps {
  allocations: SleeveAllocation[];
}

export function SleeveAllocationsTable({ allocations }: SleeveAllocationsTableProps) {
  const formatCurrency = (value: string) => {
    return new Intl.NumberFormat('en-GB', {
      style: 'currency',
      currency: 'GBP',
      minimumFractionDigits: 0,
    }).format(parseFloat(value));
  };

  const formatPercent = (value: string) => {
    return `${parseFloat(value).toFixed(2)}%`;
  };

  const getDriftColor = (drift: string, isDrifted: boolean) => {
    if (!isDrifted) return 'text-gray-600';
    const driftVal = parseFloat(drift);
    if (driftVal > 0) return 'text-green-600';
    return 'text-red-600';
  };

  return (
    <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
      <div className="p-6 border-b border-gray-100">
        <h2 className="text-lg font-semibold text-gray-900">Sleeve Allocations vs Targets</h2>
        <p className="text-sm text-gray-500 mt-1">
          Current weight vs target weight by sleeve
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead className="bg-gray-50 border-b border-gray-200 text-xs uppercase tracking-wider text-gray-500 font-bold">
            <tr>
              <th className="p-4 text-left">Sleeve</th>
              <th className="p-4 text-right">Target Weight</th>
              <th className="p-4 text-right">Current Weight</th>
              <th className="p-4 text-right">Current Value</th>
              <th className="p-4 text-right">Drift</th>
              <th className="p-4 text-center">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 text-sm">
            {allocations.map((allocation) => (
              <tr key={allocation.sleeve_code} className="hover:bg-gray-50">
                <td className="p-4">
                  <div className="font-semibold text-gray-900">{allocation.sleeve_code}</div>
                  <div className="text-xs text-gray-500">{allocation.sleeve_name}</div>
                </td>
                <td className="p-4 text-right font-mono">
                  {formatPercent(allocation.target_weight_pct)}
                </td>
                <td className="p-4 text-right font-mono">
                  {formatPercent(allocation.current_weight_pct)}
                </td>
                <td className="p-4 text-right font-mono">
                  {formatCurrency(allocation.current_value_gbp)}
                </td>
                <td className={`p-4 text-right font-mono font-semibold ${getDriftColor(allocation.drift_pct, allocation.is_drifted)}`}>
                  {allocation.drift_pct > '0' ? '+' : ''}{formatPercent(allocation.drift_pct)}
                </td>
                <td className="p-4 text-center">
                  {allocation.is_drifted ? (
                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-semibold bg-yellow-100 text-yellow-700">
                      ⚠️ Drifted
                    </span>
                  ) : (
                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-semibold bg-green-100 text-green-700">
                      ✓ On Target
                    </span>
                  )}
                </td>
              </tr>
            ))}
            {allocations.length === 0 && (
              <tr>
                <td colSpan={6} className="p-8 text-center text-gray-500">
                  No sleeve allocations configured
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
