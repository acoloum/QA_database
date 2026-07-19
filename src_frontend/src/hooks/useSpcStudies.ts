import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import type {
  SpcAssignee, SpcEventSummary, SpcLimitVersionSummary, SpcOcapRecord,
  SpcOcapStatus, SpcStudyHistoryPage, SpcStudyResult, SpcStudySummary,
  SpcStudyVersionSummary,
} from '../types';

interface ApiSuccess<T> {
  success: true;
  data: T;
}

export interface AnalyzeSpcStudyInput {
  source: 'shipping' | 'patrol';
  filters: Record<string, unknown>;
  study_type?: 'retrospective' | 'ongoing';
}

export interface SpcStudyActionInput {
  versionId: number;
  studyId: number;
  reason: string;
}

export interface ConfirmSpcTimeModelInput extends SpcStudyActionInput {
  model: 'A1' | 'A2';
}

export interface SpcRetireLimitInput {
  limitId: number;
  studyId: number;
  reason: string;
}

export interface SpcOcapInput {
  eventId: number;
  ocapId?: number;
  payload: {
    status?: SpcOcapStatus;
    investigation_6m?: Record<string, unknown> | null;
    remeasurement?: Record<string, unknown> | null;
    process_adjustment?: string;
    product_disposition?: string;
    effectiveness?: string;
    owner_id?: number | null;
  };
}

const unwrap = <T,>(response: { data: ApiSuccess<T> }): T => response.data.data;

const invalidateStudy = (
  queryClient: ReturnType<typeof useQueryClient>,
  studyId: number,
) => {
  queryClient.invalidateQueries({ queryKey: ['spcStudies'] });
  queryClient.invalidateQueries({ queryKey: ['spcStudy', studyId] });
  queryClient.invalidateQueries({ queryKey: ['spcStudyHistory', studyId] });
};

export const useSpcStudies = () => useQuery({
  queryKey: ['spcStudies'],
  queryFn: async () => unwrap(
    await api.get<ApiSuccess<SpcStudySummary[]>>('/spc/studies'),
  ),
});

export const useSpcStudy = (studyId: number | null) => useQuery({
  queryKey: ['spcStudy', studyId],
  queryFn: async () => unwrap(
    await api.get<ApiSuccess<SpcStudySummary>>(`/spc/studies/${studyId}`),
  ),
  enabled: studyId != null,
});

export const useSpcStudyHistory = (
  studyId: number | null, page = 1, perPage = 20,
) => useQuery({
  queryKey: ['spcStudyHistory', studyId, page, perPage],
  queryFn: async () => unwrap(
    await api.get<ApiSuccess<SpcStudyHistoryPage>>(`/spc/studies/${studyId}/history`, {
      params: { page, per_page: perPage },
    }),
  ),
  enabled: studyId != null,
});

export const fetchSpcEvent = async (eventId: number): Promise<SpcEventSummary> => unwrap(
  await api.get<ApiSuccess<SpcEventSummary>>(`/spc/events/${eventId}`),
);

export const useSpcAssignees = (enabled = true) => useQuery({
  queryKey: ['spcAssignees'],
  queryFn: async () => unwrap(
    await api.get<ApiSuccess<SpcAssignee[]>>('/spc/assignees'),
  ),
  enabled,
});

export const useAnalyzeSpcStudy = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: AnalyzeSpcStudyInput) => unwrap(
      await api.post<ApiSuccess<SpcStudyResult>>('/spc/studies/analyze', input),
    ),
    onSuccess: (version) => invalidateStudy(queryClient, version.study_id),
  });
};

export const useSubmitSpcStudy = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ versionId, reason }: SpcStudyActionInput) => unwrap(
      await api.post<ApiSuccess<SpcStudyVersionSummary>>(
        `/spc/study-versions/${versionId}/submit`, { reason },
      ),
    ),
    onSuccess: (_version, input) => invalidateStudy(queryClient, input.studyId),
  });
};

export const useConfirmSpcTimeModel = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ versionId, model, reason }: ConfirmSpcTimeModelInput) => unwrap(
      await api.post<ApiSuccess<SpcStudyVersionSummary>>(
        `/spc/study-versions/${versionId}/time-model`, { model, reason },
      ),
    ),
    onSuccess: (_version, input) => invalidateStudy(queryClient, input.studyId),
  });
};

export const useApproveSpcStudy = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ versionId, reason }: SpcStudyActionInput) => unwrap(
      await api.post<ApiSuccess<SpcLimitVersionSummary>>(
        `/spc/study-versions/${versionId}/approve`, { reason },
      ),
    ),
    onSuccess: (_limit, input) => invalidateStudy(queryClient, input.studyId),
  });
};

export const useRejectSpcStudy = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ versionId, reason }: SpcStudyActionInput) => unwrap(
      await api.post<ApiSuccess<SpcStudyVersionSummary>>(
        `/spc/study-versions/${versionId}/reject`, { reason },
      ),
    ),
    onSuccess: (_version, input) => invalidateStudy(queryClient, input.studyId),
  });
};

export const useRetireSpcLimit = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ limitId, reason }: SpcRetireLimitInput) => unwrap(
      await api.post<ApiSuccess<Pick<SpcLimitVersionSummary, 'id' | 'status'>>>(
        `/spc/limit-versions/${limitId}/retire`, { reason },
      ),
    ),
    onSuccess: (_limit, input) => invalidateStudy(queryClient, input.studyId),
  });
};

export const useSaveSpcOcap = () => useMutation({
    mutationFn: async ({ eventId, ocapId, payload }: SpcOcapInput) => unwrap(
      ocapId == null
        ? await api.post<ApiSuccess<SpcOcapRecord>>(`/spc/events/${eventId}/ocap`, payload)
        : await api.patch<ApiSuccess<SpcOcapRecord>>(`/spc/ocap/${ocapId}`, payload),
    ),
  });
