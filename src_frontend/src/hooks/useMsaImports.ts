import { useMutation, useQueryClient } from '@tanstack/react-query';

import api from '../services/api';
import type {
  ConfirmMsaEquipmentImportInput,
  EquipmentImportBatch,
  PreviewMsaEquipmentImportInput,
} from '../types/msa';
import { msaKeys } from './useMsaEquipment';

interface ApiEnvelope<T> {
  data: T;
}

const unwrap = <T,>(response: { data: ApiEnvelope<T> }): T => response.data.data;

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
      queryClient.invalidateQueries({ queryKey: msaKeys.equipmentRoot });
    },
  });
};
