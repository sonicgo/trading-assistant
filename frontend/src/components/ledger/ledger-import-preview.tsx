'use client';

import { useState, useRef } from 'react';
import { usePreviewLedgerImport, useApplyLedgerImport } from '@/hooks/use-ledger-import';
import type { CsvImportPreviewResponse, ProposedLedgerEntry, EntryKind } from '@/types';

interface LedgerImportPreviewProps {
  portfolioId: string;
}

const ENTRY_KIND_LABELS: Record<EntryKind, string> = {
  CONTRIBUTION: 'Contribution',
  BUY: 'Buy',
  SELL: 'Sell',
  ADJUSTMENT: 'Adjustment',
  REVERSAL: 'Reversal',
};

export function LedgerImportPreview({ portfolioId }: LedgerImportPreviewProps) {
  const [preview, setPreview] = useState<CsvImportPreviewResponse | null>(null);
  const [error, setError] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const previewMutation = usePreviewLedgerImport(portfolioId);
  const applyMutation = useApplyLedgerImport(portfolioId);

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setError('');
    setPreview(null);

    try {
      const base64 = await fileToBase64(file);
      const result = await previewMutation.mutateAsync({
        csv_profile: 'positions_gbp_v1',
        file_content_base64: base64.split(',')[1],
      });
      setPreview(result);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to preview CSV');
    } finally {
      setIsUploading(false);
    }
  };

  const handleApply = async () => {
    if (!preview) return;

    setError('');
    try {
      await applyMutation.mutateAsync({
        csv_profile: preview.csv_profile,
        plan_hash: preview.plan_hash,
        source_file_sha256: preview.source_file_sha256,
        effective_at: preview.effective_at,
        basis: preview.basis,
        proposed_entries: preview.proposed_entries,
      });
      
      setPreview(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (err.response?.status === 409) {
        setError('Snapshot versions have changed. Please generate a fresh preview.');
      } else {
        setError(detail || 'Failed to apply import');
      }
    }
  };

  const fileToBase64 = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  };

  const formatAmount = (amount: string | null) => {
    if (!amount) return '-';
    const num = parseFloat(amount);
    return num.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
      <h3 className="text-lg font-bold text-gray-900 mb-4">Import from CSV</h3>

      {error && (
        <div className="mb-4 p-3 bg-red-50 text-red-600 rounded-lg text-sm">
          {error}
        </div>
      )}

      {!preview ? (
        <div className="space-y-4">
          <div className="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center">
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              onChange={handleFileSelect}
              className="hidden"
              id="csv-upload"
            />
            <label
              htmlFor="csv-upload"
              className="cursor-pointer block"
            >
              <div className="text-4xl mb-3">📄</div>
              <p className="text-sm text-gray-600 mb-2">
                Click to upload a CSV file
              </p>
              <p className="text-xs text-gray-400">
                Supports positions_gbp_v1 format
              </p>
            </label>
          </div>

          {isUploading && (
            <div className="text-center text-sm text-gray-600">
              Analyzing CSV...
            </div>
          )}

          {previewMutation.error && (
            <div className="p-3 bg-red-50 text-red-600 rounded-lg text-sm">
              Failed to preview. Check the CSV format.
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-gray-50 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold font-mono tabular-nums text-gray-900">{preview.summary.holding_rows}</div>
              <div className="text-xs text-gray-500">Holdings</div>
            </div>
            <div className="bg-gray-50 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold font-mono tabular-nums text-gray-900">{preview.summary.cash_rows}</div>
              <div className="text-xs text-gray-500">Cash Rows</div>
            </div>
            <div className="bg-gray-50 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold font-mono tabular-nums text-amber-600">{preview.summary.warnings}</div>
              <div className="text-xs text-gray-500">Warnings</div>
            </div>
            <div className="bg-gray-50 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold font-mono tabular-nums text-rose-600">{preview.summary.errors}</div>
              <div className="text-xs text-gray-500">Errors</div>
            </div>
          </div>

          {preview.errors.length > 0 && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <h4 className="font-semibold text-red-800 mb-2">Errors</h4>
              <ul className="text-sm text-red-700 space-y-1">
                {preview.errors.map((err, i) => (
                  <li key={i}>
                    {err.row_number ? `Row ${err.row_number}: ` : ''}
                    {err.field ? `${err.field}: ` : ''}
                    {err.message}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {preview.warnings.length > 0 && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
              <h4 className="font-semibold text-yellow-800 mb-2">Warnings</h4>
              <ul className="text-sm text-yellow-700 space-y-1">
                {preview.warnings.map((warn, i) => (
                  <li key={i}>{warn.message}</li>
                ))}
              </ul>
            </div>
          )}

          {preview.proposed_entries.length > 0 && (
            <div>
              <h4 className="font-semibold text-gray-900 mb-3">Proposed Actions</h4>
              <div className="border border-gray-200 rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-gray-50 border-b border-gray-200 text-xs uppercase tracking-wider text-gray-500 font-bold z-10">
                    <tr>
                      <th className="p-3 text-left">Type</th>
                      <th className="p-3 text-right">Quantity</th>
                      <th className="p-3 text-right">Cash Impact</th>
                      <th className="p-3 text-left">Note</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {preview.proposed_entries.map((entry, i) => (
                      <tr key={i} className="hover:bg-gray-50">
                        <td className="p-3">
                          <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-semibold ${
                            entry.entry_kind === 'ADJUSTMENT' ? 'bg-amber-100 text-amber-800' :
                            entry.entry_kind === 'BUY' ? 'bg-blue-100 text-blue-800' :
                            entry.entry_kind === 'SELL' ? 'bg-orange-100 text-orange-800' :
                            entry.entry_kind === 'CONTRIBUTION' ? 'bg-emerald-100 text-emerald-800' :
                            'bg-gray-100 text-gray-800'
                          }`}>
                            {entry.entry_kind === 'ADJUSTMENT' && '⚠️ '}
                            {ENTRY_KIND_LABELS[entry.entry_kind]}
                          </span>
                        </td>
                        <td className="p-3 text-right">
                          {entry.quantity_delta ? (
                            <span className={`font-mono tabular-nums ${parseFloat(entry.quantity_delta) >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                              {parseFloat(entry.quantity_delta) >= 0 ? '+' : ''}
                              {formatAmount(entry.quantity_delta)}
                            </span>
                          ) : (
                            <span className="font-mono tabular-nums text-gray-400">-</span>
                          )}
                        </td>
                        <td className="p-3 text-right">
                          <span className={`font-mono tabular-nums ${parseFloat(entry.net_cash_delta_gbp) >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                            {parseFloat(entry.net_cash_delta_gbp) >= 0 ? '+' : ''}
                            £{formatAmount(entry.net_cash_delta_gbp)}
                          </span>
                        </td>
                        <td className="p-3 text-gray-600 text-xs">
                          {entry.note || '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={() => {
                setPreview(null);
                if (fileInputRef.current) {
                  fileInputRef.current.value = '';
                }
              }}
              className="px-4 py-2 border border-gray-300 rounded-lg font-semibold hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              onClick={handleApply}
              disabled={preview.errors.length > 0}
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-50"
            >
              {applyMutation.isPending ? 'Applying...' : `Apply ${preview.proposed_entries.length} Entries`}
            </button>
          </div>

          {preview.errors.length > 0 && (
            <p className="text-sm text-red-600 text-center">
              Fix errors before applying
            </p>
          )}
        </div>
      )}
    </div>
  );
}
