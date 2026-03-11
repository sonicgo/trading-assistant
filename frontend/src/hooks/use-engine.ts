import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import type { TradePlanResponse } from '@/types';

const ENGINE_KEY = 'engine';

export function useTradePlan(portfolioId: string | undefined) {
  return useQuery({
    queryKey: [ENGINE_KEY, portfolioId, 'plan'],
    queryFn: async () => {
      const res = await api.get<TradePlanResponse>(`/portfolios/${portfolioId}/engine/plan`);
      return res.data;
    },
    enabled: !!portfolioId,
    staleTime: 5 * 60 * 1000,
  });
}