import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import type { 
  Listing, 
  ListingCreate, 
  ListingUpdate, 
  ListingsPage 
} from '@/types';

const LISTINGS_KEY = 'listings';

interface ListingsFilters {
  limit?: number;
  offset?: number;
  instrument_id?: string;
  exchange?: string;
  ticker?: string;
}

export function useListings(filters: ListingsFilters = {}) {
  const { limit = 50, offset = 0, instrument_id, exchange, ticker } = filters;
  
  return useQuery({
    queryKey: [LISTINGS_KEY, { limit, offset, instrument_id, exchange, ticker }],
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set('limit', String(limit));
      params.set('offset', String(offset));
      if (instrument_id) params.set('instrument_id', instrument_id);
      if (exchange) params.set('exchange', exchange);
      if (ticker) params.set('ticker', ticker);
      
      const res = await api.get<ListingsPage>(`/registry/listings?${params}`);
      return res.data;
    },
  });
}

export function useCreateListing() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (data: ListingCreate) => {
      const res = await api.post<Listing>('/registry/listings', data);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [LISTINGS_KEY] });
    },
  });
}

export function useUpdateListing(listingId: string) {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (data: ListingUpdate) => {
      const res = await api.patch<Listing>(`/registry/listings/${listingId}`, data);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [LISTINGS_KEY] });
    },
  });
}
