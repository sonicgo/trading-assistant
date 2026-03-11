import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import type {
  LedgerBatch,
  LedgerEntry,
  LedgerBatchCreate,
  LedgerReversalRequest,
  LedgerBatchesPage,
  LedgerEntriesPage,
  EntryKind,
  BatchSource,
} from '@/types';

const LEDGER_KEY = 'ledger';
const ENTRIES_KEY = 'entries';

export function useLedgerBatches(
  portfolioId: string | undefined,
  params?: { limit?: number; offset?: number; source?: BatchSource }
) {
  return useQuery({
    queryKey: [LEDGER_KEY, portfolioId, 'batches', params],
    queryFn: async () => {
      const searchParams = new URLSearchParams();
      if (params?.limit) searchParams.set('limit', params.limit.toString());
      if (params?.offset) searchParams.set('offset', params.offset.toString());
      if (params?.source) searchParams.set('source', params.source);
      
      const queryString = searchParams.toString();
      const url = `/portfolios/${portfolioId}/ledger/batches${queryString ? `?${queryString}` : ''}`;
      
      const res = await api.get<LedgerBatchesPage>(url);
      return res.data;
    },
    enabled: !!portfolioId,
  });
}

export function useLedgerEntries(
  portfolioId: string | undefined,
  params?: { limit?: number; offset?: number; entry_kind?: EntryKind; listing_id?: string }
) {
  return useQuery({
    queryKey: [ENTRIES_KEY, portfolioId, params],
    queryFn: async () => {
      const searchParams = new URLSearchParams();
      if (params?.limit) searchParams.set('limit', params.limit.toString());
      if (params?.offset) searchParams.set('offset', params.offset.toString());
      if (params?.entry_kind) searchParams.set('entry_kind', params.entry_kind);
      if (params?.listing_id) searchParams.set('listing_id', params.listing_id);
      
      const queryString = searchParams.toString();
      const url = `/portfolios/${portfolioId}/ledger/entries${queryString ? `?${queryString}` : ''}`;
      
      const res = await api.get<LedgerEntriesPage>(url);
      return res.data;
    },
    enabled: !!portfolioId,
  });
}

export function useCreateLedgerBatch(portfolioId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: LedgerBatchCreate) => {
      const res = await api.post<LedgerBatch>(`/portfolios/${portfolioId}/ledger/batches`, data);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [LEDGER_KEY, portfolioId] });
      queryClient.invalidateQueries({ queryKey: [ENTRIES_KEY, portfolioId] });
      queryClient.invalidateQueries({ queryKey: ['snapshots', portfolioId] });
    },
  });
}

export function useReverseLedgerEntries(portfolioId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: LedgerReversalRequest) => {
      const res = await api.post<LedgerBatch>(`/portfolios/${portfolioId}/ledger/reversals`, data);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [LEDGER_KEY, portfolioId] });
      queryClient.invalidateQueries({ queryKey: [ENTRIES_KEY, portfolioId] });
      queryClient.invalidateQueries({ queryKey: ['snapshots', portfolioId] });
    },
  });
}
