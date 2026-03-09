import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import type { Alert } from '@/types';

const ALERTS_KEY = 'alerts';

export function useAlerts(portfolioId: string | undefined, activeOnly?: boolean) {
  return useQuery({
    queryKey: [ALERTS_KEY, portfolioId, { active_only: activeOnly }],
    queryFn: async () => {
      const res = await api.get<Alert[]>(
        `/portfolios/${portfolioId}/alerts?active_only=${activeOnly ?? true}`
      );
      return res.data;
    },
    enabled: !!portfolioId,
  });
}
