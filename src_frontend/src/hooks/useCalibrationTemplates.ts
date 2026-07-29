import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import api from '../services/api';
import type {
  CalibrationPage,
  CalibrationTemplate,
  CalibrationTemplateListParams,
  CalibrationTemplateVersion,
  CalibrationTemplateVersionInput,
  CreateCalibrationTemplateInput,
  UpdateCalibrationTemplateVersionInput,
} from '../types/calibration';

interface ApiEnvelope<T> {
  data: T;
}

const unwrap = <T,>(response: { data: ApiEnvelope<T> }): T => response.data.data;

export const calibrationKeys = {
  all: ['calibration'] as const,
  templateLists: () => ['calibration', 'templates', 'list'] as const,
  templateList: (params: CalibrationTemplateListParams) => (
    ['calibration', 'templates', 'list', params] as const
  ),
  template: (id: number) => ['calibration', 'templates', 'detail', id] as const,
  recordLists: () => ['calibration', 'records', 'list'] as const,
  recordList: (params: unknown) => (
    ['calibration', 'records', 'list', params] as const
  ),
  record: (id: number) => ['calibration', 'records', 'detail', id] as const,
};

export const isCalibrationTemplateListQuery = (
  query: { queryKey: readonly unknown[] },
) => {
  const key = query.queryKey;
  return key[0] === 'calibration'
    && key[1] === 'templates'
    && key[2] === 'list'
    && typeof key[3] === 'object'
    && key[3] !== null
    && !Array.isArray(key[3]);
};

const invalidateTemplate = (
  queryClient: ReturnType<typeof useQueryClient>,
  templateId?: number,
) => {
  queryClient.invalidateQueries({ predicate: isCalibrationTemplateListQuery });
  if (templateId != null) {
    queryClient.invalidateQueries({
      queryKey: calibrationKeys.template(templateId),
    });
  }
};

export const useCalibrationTemplates = (
  params: CalibrationTemplateListParams,
) => useQuery({
  queryKey: calibrationKeys.templateList(params),
  queryFn: async () => unwrap(
    await api.get<ApiEnvelope<CalibrationPage<CalibrationTemplate>>>(
      '/calibration-templates',
      { params },
    ),
  ),
});

export const useCalibrationTemplate = (templateId: number | null) => useQuery({
  queryKey: calibrationKeys.template(templateId ?? 0),
  queryFn: async () => unwrap(
    await api.get<ApiEnvelope<CalibrationTemplate>>(
      `/calibration-templates/${templateId}`,
    ),
  ),
  enabled: templateId != null,
});

export const useCreateCalibrationTemplate = () => {
  const queryClient = useQueryClient();
  return useMutation<
    CalibrationTemplate,
    unknown,
    CreateCalibrationTemplateInput
  >({
    mutationFn: async (payload) => unwrap(
      await api.post<ApiEnvelope<CalibrationTemplate>>(
        '/calibration-templates',
        payload,
      ),
    ),
    onSuccess: () => invalidateTemplate(queryClient),
  });
};

export const useCreateCalibrationTemplateVersion = () => {
  const queryClient = useQueryClient();
  return useMutation<
    CalibrationTemplateVersion,
    unknown,
    CalibrationTemplateVersionInput & { templateId: number }
  >({
    mutationFn: async ({ templateId, ...payload }) => unwrap(
      await api.post<ApiEnvelope<CalibrationTemplateVersion>>(
        `/calibration-templates/${templateId}/versions`,
        payload,
      ),
    ),
    onSuccess: (_version, { templateId }) => (
      invalidateTemplate(queryClient, templateId)
    ),
  });
};

export const useUpdateCalibrationTemplateVersion = () => {
  const queryClient = useQueryClient();
  return useMutation<
    CalibrationTemplateVersion,
    unknown,
    UpdateCalibrationTemplateVersionInput
  >({
    mutationFn: async ({ templateId: _templateId, versionId, ...payload }) => (
      unwrap(await api.patch<ApiEnvelope<CalibrationTemplateVersion>>(
        `/calibration-template-versions/${versionId}`,
        payload,
      ))
    ),
    onSuccess: (_version, { templateId }) => (
      invalidateTemplate(queryClient, templateId)
    ),
  });
};

type TemplateDecisionInput = {
  templateId: number;
  versionId: number;
  expected_version: number;
  reason?: string;
};

const useTemplateDecision = (action: 'submit' | 'approve' | 'reject') => {
  const queryClient = useQueryClient();
  return useMutation<
    CalibrationTemplateVersion,
    unknown,
    TemplateDecisionInput
  >({
    mutationFn: async ({ templateId: _templateId, versionId, ...payload }) => (
      unwrap(await api.post<ApiEnvelope<CalibrationTemplateVersion>>(
        `/calibration-template-versions/${versionId}/${action}`,
        payload,
      ))
    ),
    onSuccess: (_version, { templateId }) => (
      invalidateTemplate(queryClient, templateId)
    ),
  });
};

export const useSubmitCalibrationTemplateVersion = () => (
  useTemplateDecision('submit')
);
export const useApproveCalibrationTemplateVersion = () => (
  useTemplateDecision('approve')
);
export const useRejectCalibrationTemplateVersion = () => (
  useTemplateDecision('reject')
);
