import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import type { FreezeState, FreezeStatus } from '@/types';

const FREEZE_KEY = 'freeze';

export function useFreeze(portfolioId: string | undefined) {
  return useQuery({
    queryKey: [FREEZE_KEY, portfolioId],
    queryFn: async () => {
      const res = await api.get<FreezeStatus>(`/portfolios/${portfolioId}/freeze`);
      return res.data;
    },
    enabled: !!portfolioId,
  });
}

export function useFreezePortfolio(portfolioId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      const res = await api.post<FreezeState>(`/portfolios/${portfolioId}/freeze`);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FREEZE_KEY, portfolioId] });
    },
  });
}

export function useUnfreezePortfolio(portfolioId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      const res = await api.post<FreezeState>(`/portfolios/${portfolioId}/unfreeze`);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FREEZE_KEY, portfolioId] });
    },
  });
}
