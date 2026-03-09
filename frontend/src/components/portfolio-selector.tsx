'use client';

import { usePortfolios } from '@/hooks/use-portfolios-query';
import type { Portfolio } from '@/types';

interface PortfolioSelectorProps {
  selectedId?: string;
  onSelect: (id: string) => void;
}

export function PortfolioSelector({
  selectedId,
  onSelect,
}: PortfolioSelectorProps) {
  const { data: portfolios, isLoading } = usePortfolios();

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    onSelect(e.target.value);
  };

  return (
    <div className="min-w-[300px]">
      <label className="block text-sm font-semibold text-gray-700 mb-2">
        Portfolio
      </label>
      <select
        value={selectedId || ''}
        onChange={handleChange}
        className="w-full p-3 border rounded-xl bg-gray-50 text-sm"
      >
        <option value="">
          {isLoading ? 'Loading...' : 'Select a portfolio'}
        </option>
        {!isLoading && portfolios && portfolios.length === 0 && (
          <option disabled>No portfolios available</option>
        )}
        {portfolios?.map((portfolio: Portfolio) => (
          <option key={portfolio.portfolio_id} value={portfolio.portfolio_id}>
            {portfolio.name} ({portfolio.tax_profile}) — {portfolio.base_currency}
          </option>
        ))}
      </select>
    </div>
  );
}
