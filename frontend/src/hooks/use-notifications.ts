import { useQuery } from '@tanstack/react-query';
import type { Notification } from '@/types';
import { api } from '@/lib/api-client';

const NOTIFICATIONS_KEY = 'notifications';

/**
 * Hook to fetch notifications with polling.
 * Polls every 30 seconds for new notifications since the provided timestamp.
 *
 * @param since - Optional ISO timestamp to fetch notifications after this time
 * @returns useQuery result with Notification[] data
 */
export function useNotifications(since?: string) {
  return useQuery({
    queryKey: [NOTIFICATIONS_KEY, { since }],
    queryFn: async (): Promise<Notification[]> => {
      const res = await api.get<Notification[]>(
        `/notifications?since=${since || ''}`
      );
      return res.data;
    },
    refetchInterval: 30000, // Poll every 30 seconds
  });
}
