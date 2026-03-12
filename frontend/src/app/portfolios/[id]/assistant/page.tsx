'use client';

import { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import { TradePlan } from '@/components/engine/trade-plan';

export default function AssistantPage() {
  const { id } = useParams();
  const router = useRouter();
  const portfolioId = id as string;
  const { user, isLoading: authLoading } = useAuth();

  useEffect(() => {
    if (!authLoading && !user) router.push('/login');
  }, [user, authLoading, router]);

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-6xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.push(`/portfolios/${portfolioId}`)}
              className="text-sm text-blue-600 hover:underline"
            >
              ← Back to Portfolio
            </button>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Trade Assistant</h1>
        </div>

        <TradePlan portfolioId={portfolioId} />
      </div>
    </div>
  );
}
