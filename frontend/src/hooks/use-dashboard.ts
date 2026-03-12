import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import type { PortfolioDashboardSummary } from '@/types';

const DASHBOARD_KEY = 'dashboard';

export function useDashboardSummary(portfolioId: string | undefined) {
  return useQuery({
    queryKey: [DASHBOARD_KEY, portfolioId, 'summary'],
    queryFn: async () => {
      const res = await api.get<PortfolioDashboardSummary>(
        `/portfolios/${portfolioId}/dashboard/summary`
      );
      return res.data;
    },
    enabled: !!portfolioId,
    refetchInterval: 30000,
  });
}
