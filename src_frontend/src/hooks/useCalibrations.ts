import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import api, { unwrap, type ApiEnvelope } from '../services/api';
import type {
  CalibrationDecisionInput,
  CalibrationListParams,
  CalibrationPage,
  CalibrationRecord,
  CalibrationValidationResult,
  CreateCalibrationInput,
  SaveCalibrationReadingsInput,
  UpdateCalibrationInput,
} from '../types/calibration';
import { downloadBlob } from '../utils/downloadFile';
import { calibrationKeys } from './useCalibrationTemplates';

export { calibrationKeys } from './useCalibrationTemplates';

export const isCalibrationRecordListQuery = (
  query: { queryKey: readonly unknown[] },
) => {
  const key = query.queryKey;
  return key[0] === 'calibration'
    && key[1] === 'records'
    && key[2] === 'list'
    && typeof key[3] === 'object'
    && key[3] !== null
    && !Array.isArray(key[3]);
};

const invalidateRecord = (
  queryClient: ReturnType<typeof useQueryClient>,
  calibrationId?: number,
) => {
  if (calibrationId != null) {
    queryClient.invalidateQueries({
      queryKey: calibrationKeys.record(calibrationId),
    });
  }
  queryClient.invalidateQueries({ predicate: isCalibrationRecordListQuery });
};

export const useCalibrations = (params: CalibrationListParams) => useQuery({
  queryKey: calibrationKeys.recordList(params),
  queryFn: async () => unwrap(
    await api.get<ApiEnvelope<CalibrationPage<CalibrationRecord>>>(
      '/calibrations',
      { params },
    ),
  ),
});

export const useCalibration = (calibrationId: number | null) => useQuery({
  queryKey: calibrationKeys.record(calibrationId ?? 0),
  queryFn: async () => unwrap(
    await api.get<ApiEnvelope<CalibrationRecord>>(
      `/calibrations/${calibrationId}`,
    ),
  ),
  enabled: calibrationId != null,
});

export const useCreateCalibration = () => {
  const queryClient = useQueryClient();
  return useMutation<CalibrationRecord, unknown, CreateCalibrationInput>({
    mutationFn: async (payload) => unwrap(
      await api.post<ApiEnvelope<CalibrationRecord>>('/calibrations', payload),
    ),
    onSuccess: (record) => invalidateRecord(queryClient, record.id),
  });
};

export const useUpdateCalibration = () => {
  const queryClient = useQueryClient();
  return useMutation<CalibrationRecord, unknown, UpdateCalibrationInput>({
    mutationFn: async ({ calibrationId, ...payload }) => unwrap(
      await api.patch<ApiEnvelope<CalibrationRecord>>(
        `/calibrations/${calibrationId}`,
        payload,
      ),
    ),
    onSuccess: (_record, { calibrationId }) => (
      invalidateRecord(queryClient, calibrationId)
    ),
  });
};

export const useSaveCalibrationReadings = () => {
  const queryClient = useQueryClient();
  return useMutation<
    CalibrationRecord,
    unknown,
    SaveCalibrationReadingsInput
  >({
    mutationFn: async ({ calibrationId, ...payload }) => unwrap(
      await api.put<ApiEnvelope<CalibrationRecord>>(
        `/calibrations/${calibrationId}/readings`,
        payload,
      ),
    ),
    onSuccess: (_record, { calibrationId }) => (
      invalidateRecord(queryClient, calibrationId)
    ),
  });
};

export const useValidateCalibration = () => {
  const queryClient = useQueryClient();
  return useMutation<
    CalibrationValidationResult,
    unknown,
    { calibrationId: number; expected_version: number }
  >({
    mutationFn: async ({ calibrationId, ...payload }) => unwrap(
      await api.post<ApiEnvelope<CalibrationValidationResult>>(
        `/calibrations/${calibrationId}/validate`,
        payload,
      ),
    ),
    onSuccess: (_result, { calibrationId }) => (
      invalidateRecord(queryClient, calibrationId)
    ),
  });
};

const useCalibrationDecision = (
  action: 'submit' | 'approve' | 'reject' | 'void',
) => {
  const queryClient = useQueryClient();
  return useMutation<CalibrationRecord, unknown, CalibrationDecisionInput>({
    mutationFn: async ({ calibrationId, ...payload }) => unwrap(
      await api.post<ApiEnvelope<CalibrationRecord>>(
        `/calibrations/${calibrationId}/${action}`,
        payload,
      ),
    ),
    onSuccess: (_record, { calibrationId }) => (
      invalidateRecord(queryClient, calibrationId)
    ),
  });
};

export const useSubmitCalibration = () => useCalibrationDecision('submit');
export const useApproveCalibration = () => useCalibrationDecision('approve');
export const useRejectCalibration = () => useCalibrationDecision('reject');
export const useVoidCalibration = () => useCalibrationDecision('void');

export const useDownloadCalibrationCertificate = () => useMutation<
  void,
  unknown,
  { attachmentId: number; filename: string }
>({
  mutationFn: async ({ attachmentId, filename }) => {
    const response = await api.get(
      `/attachments/${attachmentId}/download`,
      { responseType: 'blob' },
    );
    downloadBlob(response.data, filename);
  },
});
