import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import type {
  CashSnapshot,
  HoldingSnapshotList,
} from '@/types';

const SNAPSHOTS_KEY = 'snapshots';

export function useCashSnapshot(portfolioId: string | undefined) {
  return useQuery({
    queryKey: [SNAPSHOTS_KEY, portfolioId, 'cash'],
    queryFn: async () => {
      const res = await api.get<CashSnapshot>(`/portfolios/${portfolioId}/snapshots/cash`);
      return res.data;
    },
    enabled: !!portfolioId,
  });
}

export function useHoldingSnapshots(portfolioId: string | undefined) {
  return useQuery({
    queryKey: [SNAPSHOTS_KEY, portfolioId, 'holdings'],
    queryFn: async () => {
      const res = await api.get<HoldingSnapshotList>(`/portfolios/${portfolioId}/snapshots/holdings`);
      return res.data;
    },
    enabled: !!portfolioId,
  });
}
