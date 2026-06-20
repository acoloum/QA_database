import type { ReworkApplication } from '../../types';

export interface ReworkListFilters {
  statusFilter: string;
  startDate: string;
  endDate: string;
}

export interface ReworkFollowUpState {
  show: boolean;
  ncmrId: number;
  ncmrNumber: string;
}

interface ApiErrorLike {
  response?: {
    data?: {
      error?: string;
    };
  };
}

export const buildReworkListQuery = ({ statusFilter, startDate, endDate }: ReworkListFilters) => {
  const params = new URLSearchParams();
  if (statusFilter) params.append('status', statusFilter);
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);
  return params.toString();
};

export const getReworkErrorMessage = (error: unknown, fallback: string) => {
  const apiError = error as ApiErrorLike;
  return apiError.response?.data?.error || fallback;
};

export const resolveReworkFollowUp = (
  rework: ReworkApplication | null | undefined,
  ncmr: { related_capa_id?: number | null; NCMR單號?: string | null } | null | undefined,
): ReworkFollowUpState | null => {
  const ncmrId = rework?.NCMR_ID;
  if (!ncmrId || ncmr?.related_capa_id) return null;

  return {
    show: true,
    ncmrId,
    ncmrNumber: rework?.ncmr_number || ncmr?.NCMR單號 || String(ncmrId),
  };
};
