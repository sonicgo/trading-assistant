'use client';

import { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import { useMarketPrices, useMarketFx, useSyncMarketData } from '@/hooks/use-market-data';

export default function MarketDataPage() {
  const { id } = useParams();
  const router = useRouter();
  const portfolioId = id as string;
  const { user, isLoading: authLoading } = useAuth();

  useEffect(() => {
    if (!authLoading && !user) router.push('/login');
  }, [user, authLoading, router]);

  const { data: prices, isLoading: pricesLoading } = useMarketPrices(portfolioId, 50);
  const { data: fxRates, isLoading: fxLoading } = useMarketFx(portfolioId, 20);
  const syncMutation = useSyncMarketData(portfolioId);

  const handleFullRefresh = () => {
    syncMutation.mutate(false); // incremental = false
  };

  const handleIncrementalRefresh = () => {
    syncMutation.mutate(true); // incremental = true
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div className="flex items-center gap-4">
            <button 
              onClick={() => router.push(`/portfolios/${portfolioId}`)}
              className="text-sm text-blue-600 hover:underline"
            >
              ← Back to Portfolio
            </button>
          </div>
        </div>

        {/* Page Title & Actions */}
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 mb-8">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Market Data</h1>
              <p className="text-sm text-gray-500 mt-1">
                View and sync market prices for portfolio holdings
              </p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={handleFullRefresh}
                disabled={syncMutation.isPending}
                className="px-4 py-2 bg-gray-100 text-gray-700 text-sm font-semibold rounded-lg hover:bg-gray-200 transition disabled:opacity-50 border border-gray-300"
              >
                {syncMutation.isPending ? '⏳ Syncing...' : '🔄 Full Refresh'}
              </button>
              <button
                onClick={handleIncrementalRefresh}
                disabled={syncMutation.isPending}
                className="px-4 py-2 bg-indigo-600 text-white text-sm font-semibold rounded-lg hover:bg-indigo-700 transition disabled:opacity-50"
              >
                {syncMutation.isPending ? '⏳ Syncing...' : '⚡ Incremental Refresh'}
              </button>
            </div>
          </div>

          {/* Sync Result */}
          {syncMutation.isSuccess && (
            <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-green-600 font-semibold">✓ Sync completed successfully</span>
              </div>
              <div className="text-sm text-gray-600 grid grid-cols-3 gap-4">
                <div>
                  <span className="font-medium">Listings:</span> {syncMutation.data.total_listings}
                </div>
                <div>
                  <span className="font-medium">Fetched:</span> {syncMutation.data.prices_fetched}
                </div>
                <div>
                  <span className="font-medium">Inserted:</span> {syncMutation.data.prices_inserted}
                </div>
              </div>
              {syncMutation.data.errors.length > 0 && (
                <div className="mt-2 text-sm text-red-600">
                  <span className="font-medium">Warnings:</span> {syncMutation.data.errors.join(', ')}
                </div>
              )}
            </div>
          )}

          {syncMutation.isError && (
            <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
              <span className="text-red-600 font-semibold">✗ Sync failed</span>
              <p className="text-sm text-red-600 mt-1">
                {syncMutation.error instanceof Error ? syncMutation.error.message : 'Unknown error'}
              </p>
            </div>
          )}
        </div>

        {/* Content Grid */}
        <div className="grid grid-cols-2 gap-8">
          {/* Price Points */}
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Latest Prices</h2>
            {authLoading || pricesLoading ? (
              <div className="animate-pulse space-y-3">
                <div className="h-10 bg-gray-200 rounded"></div>
                <div className="h-10 bg-gray-200 rounded"></div>
                <div className="h-10 bg-gray-200 rounded"></div>
              </div>
            ) : prices && prices.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200">
                      <th className="text-left py-2 px-3 font-semibold text-gray-700">Asset</th>
                      <th className="text-left py-2 px-3 font-semibold text-gray-700">Time</th>
                      <th className="text-right py-2 px-3 font-semibold text-gray-700">Price</th>
                      <th className="text-center py-2 px-3 font-semibold text-gray-700">Currency</th>
                    </tr>
                  </thead>
                  <tbody>
                    {prices.map((price) => (
                      <tr key={price.price_point_id} className="border-b border-gray-100 hover:bg-gray-50">
                        <td className="py-2 px-3">
                          <span className="font-mono font-semibold text-gray-900">{price.ticker}</span>
                        </td>
                        <td className="py-2 px-3 text-gray-600">
                          {new Date(price.as_of).toLocaleString()}
                        </td>
                        <td className="py-2 px-3 text-right font-medium">
                          {parseFloat(price.price).toFixed(4)}
                        </td>
                        <td className="py-2 px-3 text-center">
                          <span className="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded">
                            {price.currency || 'N/A'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                No price data available. Run a sync to fetch prices.
              </div>
            )}
          </div>

          {/* FX Rates */}
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4">FX Rates</h2>
            {authLoading || fxLoading ? (
              <div className="animate-pulse space-y-3">
                <div className="h-10 bg-gray-200 rounded"></div>
                <div className="h-10 bg-gray-200 rounded"></div>
                <div className="h-10 bg-gray-200 rounded"></div>
              </div>
            ) : fxRates && fxRates.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200">
                      <th className="text-left py-2 px-3 font-semibold text-gray-700">Pair</th>
                      <th className="text-right py-2 px-3 font-semibold text-gray-700">Rate</th>
                      <th className="text-left py-2 px-3 font-semibold text-gray-700">Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {fxRates.map((rate) => (
                      <tr key={rate.fx_rate_id} className="border-b border-gray-100 hover:bg-gray-50">
                        <td className="py-2 px-3">
                          <span className="font-medium">{rate.base_ccy}/{rate.quote_ccy}</span>
                        </td>
                        <td className="py-2 px-3 text-right">
                          {parseFloat(rate.rate).toFixed(6)}
                        </td>
                        <td className="py-2 px-3 text-gray-600">
                          {new Date(rate.as_of).toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                No FX rate data available.
              </div>
            )}
          </div>
        </div>

        {/* Legend */}
        <div className="mt-8 bg-blue-50 rounded-xl p-4 border border-blue-100">
          <h3 className="text-sm font-semibold text-blue-900 mb-2">Refresh Options</h3>
          <div className="text-sm text-blue-800 space-y-1">
            <p><span className="font-medium">🔄 Full Refresh:</span> Fetches prices for all holdings, regardless of when they were last updated.</p>
            <p><span className="font-medium">⚡ Incremental Refresh:</span> Only fetches prices for holdings that haven&apos;t been updated in the last 24 hours. Faster and avoids unnecessary API calls.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
