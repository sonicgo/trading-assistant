import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import type {
  RecommendationBatch,
  RecommendationLine,
  ExecuteBatchRequest,
  ExecuteBatchResponse,
  IgnoreBatchRequest,
  IgnoreBatchResponse,
} from '@/types';

const RECOMMENDATIONS_KEY = 'recommendations';
const LEDGER_KEY = 'ledger';
const ENTRIES_KEY = 'entries';
const SNAPSHOTS_KEY = 'snapshots';

export function useRecommendationBatch(
  portfolioId: string | undefined,
  batchId: string | undefined
) {
  return useQuery({
    queryKey: [RECOMMENDATIONS_KEY, portfolioId, batchId],
    queryFn: async () => {
      const res = await api.get<RecommendationBatch>(
        `/portfolios/${portfolioId}/recommendations/${batchId}`
      );
      return res.data;
    },
    enabled: !!portfolioId && !!batchId,
  });
}

export function useRecommendationBatches(
  portfolioId: string | undefined,
  params?: { status?: string; limit?: number; offset?: number }
) {
  return useQuery({
    queryKey: [RECOMMENDATIONS_KEY, portfolioId, 'list', params],
    queryFn: async () => {
      const searchParams = new URLSearchParams();
      if (params?.status) searchParams.set('status', params.status);
      if (params?.limit) searchParams.set('limit', params.limit.toString());
      if (params?.offset) searchParams.set('offset', params.offset.toString());

      const queryString = searchParams.toString();
      const url = `/portfolios/${portfolioId}/recommendations${
        queryString ? `?${queryString}` : ''
      }`;

      const res = await api.get<RecommendationBatch[]>(url);
      return res.data;
    },
    enabled: !!portfolioId,
  });
}

export function useExecuteRecommendationBatch(
  portfolioId: string | undefined,
  batchId: string | undefined
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: ExecuteBatchRequest) => {
      const res = await api.post<ExecuteBatchResponse>(
        `/portfolios/${portfolioId}/recommendations/${batchId}/execute`,
        data
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [RECOMMENDATIONS_KEY, portfolioId, batchId],
      });
      queryClient.invalidateQueries({
        queryKey: [RECOMMENDATIONS_KEY, portfolioId, 'list'],
      });
      queryClient.invalidateQueries({
        queryKey: [LEDGER_KEY, portfolioId],
      });
      queryClient.invalidateQueries({
        queryKey: [ENTRIES_KEY, portfolioId],
      });
      queryClient.invalidateQueries({
        queryKey: [SNAPSHOTS_KEY, portfolioId],
      });
    },
  });
}

export function useIgnoreRecommendationBatch(
  portfolioId: string | undefined,
  batchId: string | undefined
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: IgnoreBatchRequest) => {
      const res = await api.post<IgnoreBatchResponse>(
        `/portfolios/${portfolioId}/recommendations/${batchId}/ignore`,
        data
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [RECOMMENDATIONS_KEY, portfolioId, batchId],
      });
      queryClient.invalidateQueries({
        queryKey: [RECOMMENDATIONS_KEY, portfolioId, 'list'],
      });
    },
  });
}
