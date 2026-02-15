import { useState, useEffect } from 'react';
import { api } from '@/lib/api-client';

export function usePortfolios() {
  const [portfolios, setPortfolios] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchPortfolios = async () => {
    try {
      const res = await api.get('/portfolios/');
      setPortfolios(res.data);
    } catch (err) {
      console.error('Failed to fetch portfolios', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPortfolios();
  }, []);

  return { portfolios, loading, refresh: fetchPortfolios };
}
