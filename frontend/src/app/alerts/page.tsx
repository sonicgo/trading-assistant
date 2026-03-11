'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { PortfolioSelector } from '@/components/portfolio-selector';
import { useAlerts } from '@/hooks/use-alerts';
import { useListings } from '@/hooks/use-listings';
import type { AlertSeverity } from '@/types';

export default function AlertsPage() {
  const router = useRouter();
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string | null>(null);
  const [activeOnly, setActiveOnly] = useState(true);

  const { data: alerts, isLoading } = useAlerts(selectedPortfolioId || undefined, activeOnly);
  const { data: listings } = useListings({ limit: 200 });

  const getTicker = (listingId: string | null) => {
    if (!listingId) return null;
    const listing = listings?.items.find(l => l.listing_id === listingId);
    return listing?.ticker || null;
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const getSeverityStyles = (severity: AlertSeverity) => {
    switch (severity) {
      case 'CRITICAL':
        return {
          badge: 'bg-red-100 text-red-700',
          border: 'border-l-4 border-l-red-500',
        };
      case 'WARN':
        return {
          badge: 'bg-amber-100 text-amber-700',
          border: 'border-l-4 border-l-amber-500',
        };
      case 'INFO':
        return {
          badge: 'bg-blue-100 text-blue-700',
          border: 'border-l-4 border-l-blue-500',
        };
      default:
        return {
          badge: 'bg-gray-100 text-gray-700',
          border: 'border-l-4 border-l-gray-300',
        };
    }
  };

  const hasAlerts = alerts && alerts.length > 0;

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.push('/')}
              className="text-sm text-blue-600 hover:underline"
            >
              ← Back to Dashboard
            </button>
            <h1 className="text-3xl font-bold text-gray-900">Alerts</h1>
          </div>
        </div>

        {/* Portfolio Selector */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 mb-6">
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            Select Portfolio
          </label>
          <PortfolioSelector
            selectedId={selectedPortfolioId || undefined}
            onSelect={(id) => setSelectedPortfolioId(id)}
          />
        </div>

        {/* Active Only Toggle */}
        {selectedPortfolioId && (
          <div className="flex gap-2 mb-6">
            <button
              onClick={() => setActiveOnly(true)}
              className={`px-4 py-2 rounded-lg font-semibold transition ${
                activeOnly
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              Active Only
            </button>
            <button
              onClick={() => setActiveOnly(false)}
              className={`px-4 py-2 rounded-lg font-semibold transition ${
                !activeOnly
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              Show All
            </button>
          </div>
        )}

        {/* Alerts List */}
        <div className="space-y-4">
          {isLoading ? (
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-8">
              <div className="animate-pulse space-y-4">
                <div className="h-24 bg-gray-200 rounded-xl"></div>
                <div className="h-24 bg-gray-200 rounded-xl"></div>
                <div className="h-24 bg-gray-200 rounded-xl"></div>
              </div>
            </div>
          ) : hasAlerts ? (
            alerts.map((alert) => {
              const styles = getSeverityStyles(alert.severity);
              const ticker = getTicker(alert.listing_id);
              
              return (
                <div
                  key={alert.alert_id}
                  className={`bg-white rounded-xl border border-gray-200 shadow-sm p-4 ${styles.border}`}
                >
                  <div className="flex justify-between items-start mb-2">
                    <div className="flex items-center gap-3">
                      <span className={`text-xs font-bold px-2 py-1 rounded ${styles.badge}`}>
                        {alert.severity}
                      </span>
                      <span className="font-mono text-sm text-gray-600">
                        {alert.rule_code}
                      </span>
                      {ticker && (
                        <span className="font-mono text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">
                          {ticker}
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-gray-500">
                      {formatDate(alert.created_at)}
                    </span>
                  </div>
                  
                  <h3 className="font-bold text-gray-900 mb-1">{alert.title}</h3>
                  
                  {alert.message && (
                    <p className="text-sm text-gray-600 mb-2">{alert.message}</p>
                  )}
                  
                  {alert.resolved_at && (
                    <p className="text-xs text-gray-400">
                      Resolved: {formatDate(alert.resolved_at)}
                    </p>
                  )}
                </div>
              );
            })
          ) : selectedPortfolioId ? (
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-12 text-center">
              <div className="text-5xl mb-4">🔔</div>
              <h3 className="text-lg font-semibold text-gray-700 mb-2">
                {activeOnly ? 'No active alerts' : 'No alerts'}
              </h3>
              <p className="text-gray-500">
                {activeOnly ? 'All alerts have been resolved for this portfolio' : 'No alerts found for this portfolio'}
              </p>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-12 text-center">
              <div className="text-5xl mb-4">📊</div>
              <h3 className="text-lg font-semibold text-gray-700 mb-2">Select a Portfolio</h3>
              <p className="text-gray-500">Choose a portfolio above to view its alerts</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
