import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import type { Portfolio, PortfolioCreate, PortfolioUpdate } from '@/types';

const PORTFOLIOS_KEY = 'portfolios';

export function usePortfolios() {
  return useQuery({
    queryKey: [PORTFOLIOS_KEY],
    queryFn: async () => {
      const res = await api.get<Portfolio[]>('/portfolios');
      return res.data;
    },
  });
}

export function usePortfolio(portfolioId: string | undefined) {
  return useQuery({
    queryKey: [PORTFOLIOS_KEY, portfolioId],
    queryFn: async () => {
      const res = await api.get<Portfolio>(`/portfolios/${portfolioId}`);
      return res.data;
    },
    enabled: !!portfolioId,
  });
}

export function useCreatePortfolio() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (data: PortfolioCreate) => {
      const res = await api.post<Portfolio>('/portfolios', data);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [PORTFOLIOS_KEY] });
    },
  });
}

export function useUpdatePortfolio(portfolioId: string) {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (data: PortfolioUpdate) => {
      const res = await api.patch<Portfolio>(`/portfolios/${portfolioId}`, data);
      return res.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: [PORTFOLIOS_KEY] });
      queryClient.setQueryData([PORTFOLIOS_KEY, portfolioId], data);
    },
  });
}
