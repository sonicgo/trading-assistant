import { useQuery } from '@tanstack/react-query';
import type { Sleeve } from '@/types';
import { SLEEVES } from '@/types';

const SLEEVES_KEY = 'sleeves';

/**
 * Hook to get available sleeves for portfolio constituent mapping.
 * Currently returns hardcoded values from DB seed.
 * Can be updated to fetch from API when /registry/sleeves endpoint is added.
 */
export function useSleeves() {
  return useQuery({
    queryKey: [SLEEVES_KEY],
    queryFn: async (): Promise<Sleeve[]> => {
      // Return hardcoded sleeves from DB seed migration
      // When backend adds GET /registry/sleeves, replace with:
      // const res = await api.get<Sleeve[]>('/registry/sleeves');
      // return res.data;
      return SLEEVES;
    },
    staleTime: Infinity, // Reference data rarely changes
  });
}
