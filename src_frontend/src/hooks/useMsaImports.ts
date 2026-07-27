import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import api from '../services/api';
import type {
  ConfirmMsaEquipmentImportInput,
  EquipmentImportBatch,
  EquipmentImportBatchSummary,
  EquipmentImportHistoryParams,
  MsaPage,
  PreviewMsaEquipmentImportInput,
} from '../types/msa';
import { invalidateMsaEquipmentLists, msaKeys } from './useMsaEquipment';

interface ApiEnvelope<T> {
  data: T;
}

const unwrap = <T,>(response: { data: ApiEnvelope<T> }): T => response.data.data;

export const isMsaImportHistoryQuery = (
  query: { queryKey: readonly unknown[] },
) => (
  query.queryKey[0] === 'msa'
  && query.queryKey[1] === 'equipment-import'
  && query.queryKey[2] === 'history'
);

export const useMsaImportHistory = (params: EquipmentImportHistoryParams) => useQuery({
  queryKey: msaKeys.importHistory(params),
  queryFn: async () => unwrap(
    await api.get<ApiEnvelope<MsaPage<EquipmentImportBatchSummary>>>(
      '/measurement-equipment/imports',
      { params },
    ),
  ),
});

export const useMsaImportBatch = (batchId: number | null) => useQuery({
  queryKey: msaKeys.importBatch(batchId ?? 0),
  queryFn: async () => unwrap(
    await api.get<ApiEnvelope<EquipmentImportBatch>>(
      `/measurement-equipment/imports/${batchId}`,
    ),
  ),
  enabled: batchId != null,
});

export const usePreviewMsaEquipmentImport = () => {
  const queryClient = useQueryClient();
  return useMutation<EquipmentImportBatch, unknown, PreviewMsaEquipmentImportInput>({
    mutationFn: async ({ file, as_of }: PreviewMsaEquipmentImportInput) => {
      const formData = new FormData();
      formData.append('file', file);
      return unwrap(await api.post<ApiEnvelope<EquipmentImportBatch>>(
        '/measurement-equipment/imports/preview', formData,
        as_of ? { params: { as_of } } : undefined,
      ));
    },
    onSuccess: (batch: EquipmentImportBatch) => {
      queryClient.invalidateQueries({ queryKey: msaKeys.importBatch(batch.id) });
      queryClient.invalidateQueries({
        predicate: isMsaImportHistoryQuery,
      });
    },
  });
};

export const useConfirmMsaEquipmentImport = () => {
  const queryClient = useQueryClient();
  return useMutation<EquipmentImportBatch, unknown, ConfirmMsaEquipmentImportInput>({
    mutationFn: async ({ batchId, resolutions, confirmation_date }: ConfirmMsaEquipmentImportInput) => unwrap(
      await api.post<ApiEnvelope<EquipmentImportBatch>>(
        `/measurement-equipment/imports/${batchId}/confirm`,
        confirmation_date ? { resolutions, confirmation_date } : { resolutions },
      ),
    ),
    onSuccess: (_batch: EquipmentImportBatch, { batchId }: ConfirmMsaEquipmentImportInput) => {
      queryClient.invalidateQueries({ queryKey: msaKeys.importBatch(batchId) });
      queryClient.invalidateQueries({
        predicate: isMsaImportHistoryQuery,
      });
      invalidateMsaEquipmentLists(queryClient);
    },
  });
};
