'use client';

import { useState } from 'react';
import type { RecommendationBatch, RecommendationLine } from '@/types';
import Decimal from 'decimal.js';

interface ExecuteModalProps {
  batch: RecommendationBatch;
  onExecute: (lines: Array<{
    line_id: string;
    executed_quantity: string;
    executed_price_gbp: string;
    executed_fee_gbp: string;
    note?: string;
  }>) => void;
  onClose: () => void;
  isPending: boolean;
}

export function ExecuteModal({ batch, onExecute, onClose, isPending }: ExecuteModalProps) {
  const [lineData, setLineData] = useState<
    Record<
      string,
      {
        quantity: string;
        price: string;
        fee: string;
        note: string;
      }
    >
  >(() => {
    const initial: Record<string, { quantity: string; price: string; fee: string; note: string }> =
      {};
    batch.lines.forEach((line) => {
      initial[line.recommendation_line_id] = {
        quantity: line.proposed_quantity,
        price: line.proposed_price_gbp,
        fee: line.proposed_fee_gbp,
        note: '',
      };
    });
    return initial;
  });

  const [errors, setErrors] = useState<Record<string, string>>({});

  const updateLine = (lineId: string, field: string, value: string) => {
    setLineData((prev) => ({
      ...prev,
      [lineId]: { ...prev[lineId], [field]: value },
    }));
    if (errors[lineId]) {
      setErrors((prev) => ({ ...prev, [lineId]: '' }));
    }
  };

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};
    let isValid = true;

    batch.lines.forEach((line) => {
      const data = lineData[line.recommendation_line_id];
      try {
        const qty = new Decimal(data.quantity);
        if (qty.lessThanOrEqualTo(0)) {
          newErrors[line.recommendation_line_id] = 'Quantity must be greater than 0';
          isValid = false;
        }
      } catch {
        newErrors[line.recommendation_line_id] = 'Invalid quantity';
        isValid = false;
      }
    });

    setErrors(newErrors);
    return isValid;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    const executions = batch.lines.map((line) => ({
      line_id: line.recommendation_line_id,
      executed_quantity: lineData[line.recommendation_line_id].quantity,
      executed_price_gbp: lineData[line.recommendation_line_id].price,
      executed_fee_gbp: lineData[line.recommendation_line_id].fee,
      note: lineData[line.recommendation_line_id].note || undefined,
    }));

    onExecute(executions);
  };

  const calculateTotal = (line: RecommendationLine) => {
    const data = lineData[line.recommendation_line_id];
    try {
      const qty = new Decimal(data.quantity);
      const price = new Decimal(data.price);
      const fee = new Decimal(data.fee);
      const total = qty.times(price).plus(fee);
      return total.toFixed(2);
    } catch {
      return '-';
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        <div className="p-6 border-b border-gray-100">
          <h2 className="text-2xl font-bold text-gray-900">Execute Recommendation</h2>
          <p className="text-sm text-gray-500 mt-1">
            Enter the actual executed quantities, prices, and fees for each trade.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="flex-1 overflow-auto">
          <div className="p-6 space-y-6">
            {batch.lines.map((line) => (
              <div
                key={line.recommendation_line_id}
                className="border border-gray-200 rounded-xl p-4 space-y-4"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span
                      className={`text-sm font-bold px-2 py-1 rounded ${
                        line.action === 'BUY'
                          ? 'bg-green-100 text-green-700'
                          : 'bg-red-100 text-red-700'
                      }`}
                    >
                      {line.action}
                    </span>
                    <span className="font-mono font-bold text-gray-900">
                      Proposed: {line.proposed_quantity} @ £{line.proposed_price_gbp}
                    </span>
                  </div>
                  <div className="text-sm text-gray-500">
                    Est. Total: £{calculateTotal(line)}
                  </div>
                </div>

                {errors[line.recommendation_line_id] && (
                  <div className="text-sm text-red-600 bg-red-50 p-2 rounded">
                    {errors[line.recommendation_line_id]}
                  </div>
                )}

                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-gray-600 mb-1">
                      Executed Quantity
                    </label>
                    <input
                      type="number"
                      step="any"
                      value={lineData[line.recommendation_line_id]?.quantity || ''}
                      onChange={(e) =>
                        updateLine(line.recommendation_line_id, 'quantity', e.target.value)
                      }
                      className="w-full p-2 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-gray-600 mb-1">
                      Executed Price (£)
                    </label>
                    <input
                      type="number"
                      step="any"
                      value={lineData[line.recommendation_line_id]?.price || ''}
                      onChange={(e) =>
                        updateLine(line.recommendation_line_id, 'price', e.target.value)
                      }
                      className="w-full p-2 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-gray-600 mb-1">
                      Fee (£)
                    </label>
                    <input
                      type="number"
                      step="any"
                      value={lineData[line.recommendation_line_id]?.fee || ''}
                      onChange={(e) =>
                        updateLine(line.recommendation_line_id, 'fee', e.target.value)
                      }
                      className="w-full p-2 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1">
                    Note (optional)
                  </label>
                  <input
                    type="text"
                    value={lineData[line.recommendation_line_id]?.note || ''}
                    onChange={(e) =>
                      updateLine(line.recommendation_line_id, 'note', e.target.value)
                    }
                    placeholder="e.g., Executed via AJ Bell"
                    className="w-full p-2 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                  />
                </div>
              </div>
            ))}
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
              className="px-4 py-2 bg-green-600 text-white rounded-lg font-semibold hover:bg-green-700 disabled:opacity-50"
            >
              {isPending ? 'Executing...' : 'Execute Trades'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
