import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import type { 
  Instrument, 
  InstrumentCreate, 
  InstrumentUpdate, 
  InstrumentsPage 
} from '@/types';

const INSTRUMENTS_KEY = 'instruments';

interface InstrumentsFilters {
  limit?: number;
  offset?: number;
  q?: string;
  isin?: string;
}

export function useInstruments(filters: InstrumentsFilters = {}) {
  const { limit = 50, offset = 0, q, isin } = filters;
  
  return useQuery({
    queryKey: [INSTRUMENTS_KEY, { limit, offset, q, isin }],
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set('limit', String(limit));
      params.set('offset', String(offset));
      if (q) params.set('q', q);
      if (isin) params.set('isin', isin);
      
      const res = await api.get<InstrumentsPage>(`/registry/instruments?${params}`);
      return res.data;
    },
  });
}

export function useInstrument(instrumentId: string | undefined) {
  return useQuery({
    queryKey: [INSTRUMENTS_KEY, instrumentId],
    queryFn: async () => {
      // Instruments are returned in list, so we don't have a single GET
      // This would need to be added to backend if needed
      // For now, we'll fetch from the list and filter
      const res = await api.get<InstrumentsPage>('/registry/instruments?limit=1');
      return res.data.items[0];
    },
    enabled: !!instrumentId,
  });
}

export function useCreateInstrument() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (data: InstrumentCreate) => {
      const res = await api.post<Instrument>('/registry/instruments', data);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [INSTRUMENTS_KEY] });
    },
  });
}

export function useUpdateInstrument(instrumentId: string) {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (data: InstrumentUpdate) => {
      const res = await api.patch<Instrument>(`/registry/instruments/${instrumentId}`, data);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [INSTRUMENTS_KEY] });
    },
  });
}
