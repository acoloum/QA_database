import type { ReworkApplication } from '../../types';
import { compactParams } from '../../utils/queryParams';
import { getReworkErrorMessage } from '../../components/rework/reworkError';

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

/** 重工清單的查詢參數（供 axios `params` 使用）；空白篩選不送出。 */
export const buildReworkListQuery = ({ statusFilter, startDate, endDate }: ReworkListFilters) => (
  compactParams({
    status: statusFilter,
    start_date: startDate,
    end_date: endDate,
  })
);

export { getReworkErrorMessage };

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
