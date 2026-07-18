import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import type { SpcStudyResult, SpcStudySummary, SpcStudyVersionSummary } from '../types';

interface ApiSuccess<T> {
  success: true;
  data: T;
}

export interface AnalyzeSpcStudyInput {
  source: 'shipping' | 'patrol';
  filters: Record<string, unknown>;
}

export interface SpcStudyActionInput {
  versionId: number;
  studyId: number;
  reason: string;
}

export interface ConfirmSpcTimeModelInput extends SpcStudyActionInput {
  model: 'A1' | 'A2';
}

export interface SpcLimitVersion {
  id: number;
  study_version_id: number;
  revision: number;
  status: 'active' | 'retired';
  limits: Record<string, unknown>;
  approved_by: number;
  approved_at: string;
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
    status?: string;
    containment?: string;
    suspected_cause?: string;
    root_cause?: string;
    corrective_action?: string;
    effectiveness?: string;
    owner_id?: number | null;
    due_at?: string | null;
  };
}

export interface SpcOcapSummary {
  id: number;
  event_id: number;
  status: string;
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

export const useSpcStudyHistory = (studyId: number | null) => useQuery({
  queryKey: ['spcStudyHistory', studyId],
  queryFn: async () => unwrap(
    await api.get<ApiSuccess<SpcStudyVersionSummary[]>>(`/spc/studies/${studyId}/history`),
  ),
  enabled: studyId != null,
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
      await api.post<ApiSuccess<SpcLimitVersion>>(
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
      await api.post<ApiSuccess<Pick<SpcLimitVersion, 'id' | 'status'>>>(
        `/spc/limit-versions/${limitId}/retire`, { reason },
      ),
    ),
    onSuccess: (_limit, input) => invalidateStudy(queryClient, input.studyId),
  });
};

export const useSaveSpcOcap = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ eventId, ocapId, payload }: SpcOcapInput) => unwrap(
      ocapId == null
        ? await api.post<ApiSuccess<SpcOcapSummary>>(`/spc/events/${eventId}/ocap`, payload)
        : await api.patch<ApiSuccess<SpcOcapSummary>>(`/spc/ocap/${ocapId}`, payload),
    ),
    onSuccess: (_ocap, input) => {
      queryClient.invalidateQueries({ queryKey: ['spcEvents'] });
      queryClient.invalidateQueries({ queryKey: ['spcOcap', input.eventId] });
    },
  });
};
