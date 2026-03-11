'use client';

import { useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { PortfolioSelector } from '@/components/portfolio-selector';
import { useMarketPrices, useMarketFx, useRefreshMarketData } from '@/hooks/use-market-data';
import { useListings } from '@/hooks/use-listings';

export default function MarketDataPage() {
  const router = useRouter();
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string | null>(null);

  const { data: prices, isLoading: pricesLoading } = useMarketPrices(selectedPortfolioId || undefined);
  const { data: fxRates, isLoading: fxLoading } = useMarketFx(selectedPortfolioId || undefined);
  const { data: listings } = useListings({ limit: 200 });
  const refreshMutation = useRefreshMarketData(selectedPortfolioId || undefined);

  const getTicker = (listingId: string) => {
    const listing = listings?.items.find(l => l.listing_id === listingId);
    return listing?.ticker || listingId.slice(0, 8) + '...';
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const hasData = prices && prices.length > 0;
  const hasFxData = fxRates && fxRates.length > 0;

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
            <h1 className="text-3xl font-bold text-gray-900">Market Data</h1>
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

        {/* Refresh Button */}
        {selectedPortfolioId && (
          <div className="mb-6">
            <button
              onClick={() => refreshMutation.mutate()}
              disabled={refreshMutation.isPending}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-50 transition"
            >
              {refreshMutation.isPending ? 'Refreshing...' : 'Refresh Prices'}
            </button>
          </div>
        )}

        {/* Prices Table */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden mb-6">
          <div className="p-6 border-b border-gray-100">
            <h2 className="text-xl font-bold text-gray-900">Latest Prices</h2>
            <p className="text-sm text-gray-500 mt-1">
              {pricesLoading ? 'Loading...' : 
               hasData ? `${prices.length} price points` : 
               selectedPortfolioId ? 'No price data available' : 'Select a portfolio to view prices'}
            </p>
          </div>

          {pricesLoading ? (
            <div className="p-8">
              <div className="animate-pulse space-y-4">
                <div className="h-12 bg-gray-200 rounded"></div>
                <div className="h-12 bg-gray-200 rounded"></div>
                <div className="h-12 bg-gray-200 rounded"></div>
              </div>
            </div>
          ) : hasData ? (
            <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
              <table className="w-full text-left">
                <thead className="sticky top-0 bg-gray-50 border-b border-gray-200 text-xs uppercase tracking-wider text-gray-500 font-bold z-10">
                  <tr>
                    <th className="p-4 text-left">Ticker</th>
                    <th className="p-4 text-right">Price</th>
                    <th className="p-4 text-left">Currency</th>
                    <th className="p-4 text-left">Type</th>
                    <th className="p-4 text-left">As Of</th>
                    <th className="p-4 text-left">Source</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 text-sm">
                  {prices.map((price) => (
                    <tr key={price.price_point_id} className="hover:bg-gray-50">
                      <td className="p-4">
                        <span className="font-mono font-bold text-gray-900">
                          {getTicker(price.listing_id)}
                        </span>
                      </td>
                      <td className="p-4 text-right">
                        <span className="font-mono tabular-nums text-emerald-600">{price.price}</span>
                      </td>
                      <td className="p-4">
                        <span className="text-xs font-bold px-2 py-1 rounded bg-gray-100 text-gray-700">
                          {price.currency || '-'}
                        </span>
                      </td>
                      <td className="p-4">
                        <span className={`text-xs font-bold px-2 py-1 rounded ${
                          price.is_close
                            ? 'bg-purple-100 text-purple-700'
                            : 'bg-emerald-100 text-emerald-700'
                        }`}>
                          {price.is_close ? 'Close' : 'Live'}
                        </span>
                      </td>
                      <td className="p-4 text-gray-500 text-xs">{formatDate(price.as_of)}</td>
                      <td className="p-4 text-gray-500 text-xs">{price.source_id}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : selectedPortfolioId ? (
            <div className="p-8 text-center text-gray-500">
              No price data available for this portfolio
            </div>
          ) : (
            <div className="p-8 text-center text-gray-500">
              Select a portfolio to view market data
            </div>
          )}
        </div>

        {/* FX Rates Table */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="p-6 border-b border-gray-100">
            <h2 className="text-xl font-bold text-gray-900">FX Rates</h2>
            <p className="text-sm text-gray-500 mt-1">
              {fxLoading ? 'Loading...' : 
               hasFxData ? `${fxRates.length} FX rates` : 
               selectedPortfolioId ? 'No FX data available' : 'Select a portfolio to view FX rates'}
            </p>
          </div>

          {fxLoading ? (
            <div className="p-8">
              <div className="animate-pulse space-y-4">
                <div className="h-12 bg-gray-200 rounded"></div>
                <div className="h-12 bg-gray-200 rounded"></div>
              </div>
            </div>
          ) : hasFxData ? (
            <div className="overflow-x-auto max-h-[300px] overflow-y-auto">
              <table className="w-full text-left">
                <thead className="sticky top-0 bg-gray-50 border-b border-gray-200 text-xs uppercase tracking-wider text-gray-500 font-bold z-10">
                  <tr>
                    <th className="p-4 text-left">Pair</th>
                    <th className="p-4 text-right">Rate</th>
                    <th className="p-4 text-left">As Of</th>
                    <th className="p-4 text-left">Source</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 text-sm">
                  {fxRates.map((fx) => (
                    <tr key={fx.fx_rate_id} className="hover:bg-gray-50">
                      <td className="p-4">
                        <span className="font-mono font-bold text-gray-900">
                          {fx.base_ccy}/{fx.quote_ccy}
                        </span>
                      </td>
                      <td className="p-4 text-right">
                        <span className="font-mono tabular-nums text-emerald-600">{fx.rate}</span>
                      </td>
                      <td className="p-4 text-gray-500 text-xs">{formatDate(fx.as_of)}</td>
                      <td className="p-4 text-gray-500 text-xs">{fx.source_id}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : selectedPortfolioId ? (
            <div className="p-8 text-center text-gray-500">
              No FX data available for this portfolio
            </div>
          ) : (
            <div className="p-8 text-center text-gray-500">
              Select a portfolio to view FX rates
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
