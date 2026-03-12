import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import type {
  PolicyAllocationResponse,
  PolicyAllocationBulkUpdate,
  PolicyAllocationBulkResponse,
} from '@/types';

const ALLOCATIONS_KEY = 'allocations';

export function usePolicyAllocations(portfolioId: string | undefined) {
  return useQuery({
    queryKey: [ALLOCATIONS_KEY, portfolioId],
    queryFn: async () => {
      const res = await api.get<PolicyAllocationResponse[]>(
        `/portfolios/${portfolioId}/allocations`
      );
      return res.data;
    },
    enabled: !!portfolioId,
  });
}

export function useUpdatePolicyAllocations(portfolioId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: PolicyAllocationBulkUpdate) => {
      const res = await api.put<PolicyAllocationBulkResponse>(
        `/portfolios/${portfolioId}/allocations`,
        data
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [ALLOCATIONS_KEY, portfolioId],
      });
    },
  });
}
