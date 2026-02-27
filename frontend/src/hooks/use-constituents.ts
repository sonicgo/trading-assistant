import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import type { 
  Constituent, 
  ConstituentItem, 
  ConstituentBulkUpsertResponse 
} from '@/types';

const CONSTITUENTS_KEY = 'constituents';

export function useConstituents(portfolioId: string | undefined) {
  return useQuery({
    queryKey: [CONSTITUENTS_KEY, portfolioId],
    queryFn: async () => {
      const res = await api.get<Constituent[]>(`/portfolios/${portfolioId}/constituents`);
      return res.data;
    },
    enabled: !!portfolioId,
  });
}

export function useBulkUpsertConstituents(portfolioId: string) {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (items: ConstituentItem[]) => {
      const res = await api.put<ConstituentBulkUpsertResponse>(
        `/portfolios/${portfolioId}/constituents`,
        {
          items,
          replace_missing: true,
        }
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [CONSTITUENTS_KEY, portfolioId] });
    },
  });
}
