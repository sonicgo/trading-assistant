'use client';

import { useRouter } from 'next/navigation';

export default function RegistryHubPage() {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto">
        <button 
          onClick={() => router.push('/')}
          className="text-sm text-blue-600 hover:underline mb-6"
        >
          ← Back to Dashboard
        </button>

        <h1 className="text-3xl font-bold text-gray-900 mb-2">Asset Registry</h1>
        <p className="text-gray-500 mb-8">Manage instruments and their exchange listings.</p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Instruments Card */}
          <div
            onClick={() => router.push('/registry/instruments')}
            className="bg-white p-8 rounded-2xl border border-gray-200 shadow-sm hover:shadow-md hover:border-blue-400 transition-all cursor-pointer group"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center text-2xl">
                📋
              </div>
              <span className="text-gray-300 group-hover:text-blue-500 transition-colors">→</span>
            </div>
            <h2 className="text-xl font-bold text-gray-900 mb-2">Instruments</h2>
            <p className="text-gray-500 text-sm">
              Define global assets with ISIN, name, and type (ETF, Stock, Fund, etc.)
            </p>
          </div>

          {/* Listings Card */}
          <div
            onClick={() => router.push('/registry/listings')}
            className="bg-white p-8 rounded-2xl border border-gray-200 shadow-sm hover:shadow-md hover:border-blue-400 transition-all cursor-pointer group"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center text-2xl">
                🏛️
              </div>
              <span className="text-gray-300 group-hover:text-blue-500 transition-colors">→</span>
            </div>
            <h2 className="text-xl font-bold text-gray-900 mb-2">Listings</h2>
            <p className="text-gray-500 text-sm">
              Map instruments to specific exchanges with ticker symbols, currencies, and price scales.
            </p>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="mt-12 bg-white rounded-2xl border border-gray-200 shadow-sm p-6">
          <h3 className="text-lg font-bold text-gray-900 mb-4">Quick Actions</h3>
          <div className="flex flex-wrap gap-4">
            <button
              onClick={() => router.push('/registry/instruments')}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 transition"
            >
              + New Instrument
            </button>
            <button
              onClick={() => router.push('/registry/listings')}
              className="px-4 py-2 bg-green-600 text-white rounded-lg font-semibold hover:bg-green-700 transition"
            >
              + New Listing
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
