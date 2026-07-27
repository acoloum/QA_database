import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import api from '../services/api';
import type {
  ApproveMsaCalibrationInput,
  CreateMsaCalibrationInput,
  CreateMsaEquipmentInput,
  CreateMsaEquipmentLinkInput,
  EquipmentCalibration,
  EquipmentLink,
  EquipmentListParams,
  EquipmentStatusEvent,
  MeasurementEquipment,
  MeasurementEquipmentDetail,
  MeasurementEquipmentMutationResult,
  MsaPage,
  MsaStatusEventInput,
  RetireMsaEquipmentLinkInput,
  UpdateMsaEquipmentInput,
} from '../types/msa';
import { downloadBlob } from '../utils/downloadFile';

interface ApiEnvelope<T> {
  data: T;
}

const unwrap = <T,>(response: { data: ApiEnvelope<T> }): T => response.data.data;

export const msaKeys = {
  all: ['msa'] as const,
  equipmentRoot: ['msa', 'equipment'] as const,
  equipment: (params: EquipmentListParams) => ['msa', 'equipment', params] as const,
  equipmentDetail: (id: number) => ['msa', 'equipment', 'detail', id] as const,
  importBatch: (id: number, params?: { row_page: number; row_page_size: number }) => (
    ['msa', 'equipment-import', id, ...(params ? [params] : [])] as const
  ),
  importHistory: (params: { page: number; page_size: number }) => (
    ['msa', 'equipment-import', 'history', params] as const
  ),
  criteria: () => ['msa', 'criteria'] as const,
};

export const isMsaEquipmentListQuery = (query: { queryKey: readonly unknown[] }) => {
  const key = query.queryKey;
  return key[0] === 'msa'
    && key[1] === 'equipment'
    && typeof key[2] === 'object'
    && key[2] !== null
    && !Array.isArray(key[2]);
};

export const invalidateMsaEquipmentLists = (queryClient: ReturnType<typeof useQueryClient>) => {
  queryClient.invalidateQueries({ predicate: isMsaEquipmentListQuery });
};

const invalidateEquipment = (
  queryClient: ReturnType<typeof useQueryClient>,
  equipmentId?: number,
) => {
  invalidateMsaEquipmentLists(queryClient);
  if (equipmentId != null) {
    queryClient.invalidateQueries({ queryKey: msaKeys.equipmentDetail(equipmentId) });
  }
};

export const useMsaEquipment = (params: EquipmentListParams) => useQuery({
  queryKey: msaKeys.equipment(params),
  queryFn: async () => unwrap(
    await api.get<ApiEnvelope<MsaPage<MeasurementEquipment>>>('/measurement-equipment', { params }),
  ),
});

export const useMsaEquipmentDetail = (equipmentId: number | null) => useQuery({
  queryKey: msaKeys.equipmentDetail(equipmentId ?? 0),
  queryFn: async () => unwrap(
    await api.get<ApiEnvelope<MeasurementEquipmentDetail>>(`/measurement-equipment/${equipmentId}`),
  ),
  enabled: equipmentId != null,
});

export const useCreateMsaEquipment = () => {
  const queryClient = useQueryClient();
  return useMutation<MeasurementEquipmentMutationResult, unknown, CreateMsaEquipmentInput>({
    mutationFn: async (payload: CreateMsaEquipmentInput) => unwrap(
      await api.post<ApiEnvelope<MeasurementEquipment>>('/measurement-equipment', payload),
    ),
    onSuccess: () => invalidateEquipment(queryClient),
  });
};

export const useUpdateMsaEquipment = () => {
  const queryClient = useQueryClient();
  return useMutation<MeasurementEquipmentMutationResult, unknown, { equipmentId: number; payload: UpdateMsaEquipmentInput }>({
    mutationFn: async ({ equipmentId, payload }: { equipmentId: number; payload: UpdateMsaEquipmentInput }) => unwrap(
      await api.patch<ApiEnvelope<MeasurementEquipment>>(`/measurement-equipment/${equipmentId}`, payload),
    ),
    onSuccess: (
      _equipment: MeasurementEquipmentMutationResult,
      { equipmentId }: { equipmentId: number; payload: UpdateMsaEquipmentInput },
    ) => invalidateEquipment(queryClient, equipmentId),
  });
};

export const useDownloadMsaCertificate = () => useMutation<
  void,
  unknown,
  { attachmentId: number; filename: string }
>({
  mutationFn: async ({
    attachmentId,
    filename,
  }: {
    attachmentId: number;
    filename: string;
  }) => {
    const response = await api.get(
      `/attachments/${attachmentId}/download`,
      { responseType: 'blob' },
    );
    downloadBlob(response.data, filename);
  },
});

export const useMsaStatusEvent = () => {
  const queryClient = useQueryClient();
  return useMutation<EquipmentStatusEvent, unknown, MsaStatusEventInput>({
    mutationFn: async ({ equipmentId, ...payload }: MsaStatusEventInput) => unwrap(
      await api.post<ApiEnvelope<EquipmentStatusEvent>>(
        `/measurement-equipment/${equipmentId}/status-events`, payload,
      ),
    ),
    onSuccess: (_event: EquipmentStatusEvent, { equipmentId }: MsaStatusEventInput) => (
      invalidateEquipment(queryClient, equipmentId)
    ),
  });
};

export const useCreateMsaCalibration = () => {
  const queryClient = useQueryClient();
  return useMutation<EquipmentCalibration, unknown, CreateMsaCalibrationInput & { equipmentId: number }>({
    mutationFn: async ({ equipmentId, ...payload }: CreateMsaCalibrationInput & { equipmentId: number }) => unwrap(
      await api.post<ApiEnvelope<EquipmentCalibration>>(
        `/measurement-equipment/${equipmentId}/calibrations`, payload,
      ),
    ),
    onSuccess: (
      _calibration: EquipmentCalibration,
      { equipmentId }: CreateMsaCalibrationInput & { equipmentId: number },
    ) => invalidateEquipment(queryClient, equipmentId),
  });
};

export const useApproveMsaCalibration = () => {
  const queryClient = useQueryClient();
  return useMutation<EquipmentCalibration, unknown, ApproveMsaCalibrationInput>({
    mutationFn: async ({ calibrationId, equipmentId: _equipmentId, ...payload }: ApproveMsaCalibrationInput) => unwrap(
      await api.post<ApiEnvelope<EquipmentCalibration>>(
        `/measurement-equipment/calibrations/${calibrationId}/approve`, payload,
      ),
    ),
    onSuccess: (_calibration: EquipmentCalibration, { equipmentId }: ApproveMsaCalibrationInput) => (
      invalidateEquipment(queryClient, equipmentId)
    ),
  });
};

export const useCreateMsaEquipmentLink = () => {
  const queryClient = useQueryClient();
  return useMutation<EquipmentLink, unknown, CreateMsaEquipmentLinkInput>({
    mutationFn: async ({ equipmentId, ...payload }: CreateMsaEquipmentLinkInput) => unwrap(
      await api.post<ApiEnvelope<EquipmentLink>>(`/measurement-equipment/${equipmentId}/links`, payload),
    ),
    onSuccess: (_link: EquipmentLink, { equipmentId }: CreateMsaEquipmentLinkInput) => (
      invalidateEquipment(queryClient, equipmentId)
    ),
  });
};

export const useRetireMsaEquipmentLink = () => {
  const queryClient = useQueryClient();
  return useMutation<EquipmentLink, unknown, RetireMsaEquipmentLinkInput>({
    mutationFn: async ({ equipmentId, linkId, ...payload }: RetireMsaEquipmentLinkInput) => unwrap(
      await api.post<ApiEnvelope<EquipmentLink>>(
        `/measurement-equipment/${equipmentId}/links/${linkId}/retire`, payload,
      ),
    ),
    onSuccess: (_link: EquipmentLink, { equipmentId }: RetireMsaEquipmentLinkInput) => (
      invalidateEquipment(queryClient, equipmentId)
    ),
  });
};
