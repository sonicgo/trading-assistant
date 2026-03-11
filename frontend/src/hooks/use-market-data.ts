import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import type { PricePoint, FxRate, RefreshResult, SyncResult } from '@/types';

const MARKET_DATA_KEY = 'market-data';

export function useMarketPrices(portfolioId: string | undefined, limit?: number) {
  return useQuery({
    queryKey: [MARKET_DATA_KEY, 'prices', portfolioId, { limit }],
    queryFn: async () => {
      const res = await api.get<PricePoint[]>(
        `/portfolios/${portfolioId}/market-data/prices?limit=${limit || 50}`
      );
      return res.data;
    },
    enabled: !!portfolioId,
  });
}

export function useMarketFx(portfolioId: string | undefined, limit?: number) {
  return useQuery({
    queryKey: [MARKET_DATA_KEY, 'fx', portfolioId, { limit }],
    queryFn: async () => {
      const res = await api.get<FxRate[]>(
        `/portfolios/${portfolioId}/market-data/fx?limit=${limit || 50}`
      );
      return res.data;
    },
    enabled: !!portfolioId,
  });
}

export function useRefreshMarketData(portfolioId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      const res = await api.post<RefreshResult>(
        `/portfolios/${portfolioId}/market-data/refresh`
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [MARKET_DATA_KEY, 'prices', portfolioId] });
      queryClient.invalidateQueries({ queryKey: [MARKET_DATA_KEY, 'fx', portfolioId] });
    },
  });
}

export function useSyncMarketData(portfolioId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      const res = await api.post<SyncResult>(
        `/portfolios/${portfolioId}/market-data/sync`
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [MARKET_DATA_KEY, 'prices', portfolioId] });
      queryClient.invalidateQueries({ queryKey: [MARKET_DATA_KEY, 'fx', portfolioId] });
    },
  });
}
