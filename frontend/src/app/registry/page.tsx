'use client';

import { useState } from 'react';
import { api } from '@/lib/api-client';
import { useRouter } from 'next/navigation';

export default function RegistryPage() {
  const [isin, setIsin] = useState('');
  const [name, setName] = useState('');
  const [ticker, setTicker] = useState('');
  const [exchange, setExchange] = useState('LSE');
  const [status, setStatus] = useState({ type: '', message: '' });
  const router = useRouter();

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus({ type: 'info', message: 'Registering asset...' });
    
    try {
      // Step 1: Create the Instrument (The global definition)
      const instrumentRes = await api.post('/registry/instruments', {
        isin: isin.toUpperCase(),
        name,
        instrument_type: 'EQUITY' // Defaulting for Phase 1
      });

      // Step 2: Create the Primary Listing (The specific trading pair)
      await api.post('/registry/listings', {
        instrument_id: instrumentRes.data.instrument_id,
        ticker: ticker.toUpperCase(),
        exchange,
        trading_currency: 'GBP',
        quote_scale: 'GBX', // Standard for UK stocks/ETFs
        is_primary: true
      });

      setStatus({ type: 'success', message: `Successfully registered ${ticker}!` });
      // Reset form
      setIsin(''); setName(''); setTicker('');
    } catch (err: any) {
      const errorDetail = err.response?.data?.detail || 'Failed to register asset';
      setStatus({ type: 'error', message: `Error: ${errorDetail}` });
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-2xl mx-auto">
        <button 
          onClick={() => router.push('/')}
          className="text-sm text-blue-600 hover:underline mb-6"
        >
          ← Back to Dashboard
        </button>

        <h1 className="text-3xl font-bold text-gray-900 mb-2">Instrument Registry</h1>
        <p className="text-gray-500 mb-8">Define global assets and their primary exchange listings.</p>

        <form onSubmit={handleRegister} className="bg-white p-8 rounded-2xl border shadow-sm space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">ISIN</label>
              <input 
                className="w-full p-3 border rounded-xl font-mono text-sm uppercase"
                placeholder="IE00BK5BQT80"
                value={isin}
                onChange={(e) => setIsin(e.target.value)}
                required
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">Full Asset Name</label>
              <input 
                className="w-full p-3 border rounded-xl text-sm"
                placeholder="Vanguard FTSE All-World"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">Ticker Symbol</label>
              <input 
                className="w-full p-3 border rounded-xl font-mono text-sm uppercase"
                placeholder="VWRP"
                value={ticker}
                onChange={(e) => setTicker(e.target.value)}
                required
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">Primary Exchange</label>
              <select 
                className="w-full p-3 border rounded-xl text-sm bg-gray-50"
                value={exchange}
                onChange={(e) => setExchange(e.target.value)}
              >
                <option value="LSE">London Stock Exchange (LSE)</option>
                <option value="NYSE">New York Stock Exchange (NYSE)</option>
                <option value="NASDAQ">NASDAQ</option>
              </select>
            </div>
          </div>

          <button 
            type="submit"
            className="w-full bg-blue-600 text-white font-bold py-4 rounded-xl hover:bg-blue-700 transition-colors shadow-lg"
          >
            Confirm Registration
          </button>

          {status.message && (
            <div className={`p-4 rounded-xl text-sm text-center font-medium ${
              status.type === 'success' ? 'bg-green-50 text-green-700' : 
              status.type === 'error' ? 'bg-red-50 text-red-700' : 'bg-blue-50 text-blue-700'
            }`}>
              {status.message}
            </div>
          )}
        </form>
      </div>
    </div>
  );
}