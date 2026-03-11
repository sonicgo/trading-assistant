import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api-client';
import type {
  CsvImportPreviewRequest,
  CsvImportPreviewResponse,
  CsvImportApplyRequest,
  CsvImportApplyResponse,
} from '@/types';

const LEDGER_IMPORT_KEY = 'ledger-import';

export function usePreviewLedgerImport(portfolioId: string | undefined) {
  return useMutation({
    mutationFn: async (data: CsvImportPreviewRequest) => {
      const res = await api.post<CsvImportPreviewResponse>(
        `/portfolios/${portfolioId}/ledger/imports/preview`,
        data
      );
      return res.data;
    },
  });
}

export function useApplyLedgerImport(portfolioId: string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: CsvImportApplyRequest) => {
      const res = await api.post<CsvImportApplyResponse>(
        `/portfolios/${portfolioId}/ledger/imports/apply`,
        data
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ledger', portfolioId] });
      queryClient.invalidateQueries({ queryKey: ['entries', portfolioId] });
      queryClient.invalidateQueries({ queryKey: ['snapshots', portfolioId] });
    },
  });
}
