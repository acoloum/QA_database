import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import type {
  SpcAssignee, SpcEventSummary, SpcLimitVersionSummary, SpcOcapRecord,
  SpcAnalysisFamily, SpcOcapStatus, SpcStudyHistoryPage, SpcStudyResult, SpcStudySummary,
  SpcStudyVersionSummary, SpcTimeModelCode, SpcTransformationModel,
} from '../types';

export interface MachineStudyFilters {
  m_id: number;
  mat: string;
  spec: string;
  item: string;
  pos: string;
}

export interface MachineStudyOptions {
  conditions_confirmed: boolean;
  condition_reason: string;
}

interface ApiSuccess<T> {
  success: true;
  data: T;
}

interface AnalyzeSpcStudyBaseInput {
  source: 'shipping' | 'patrol' | 'mechanical';
  filters: Record<string, unknown>;
  study_type?: 'retrospective' | 'ongoing';
}

export interface AnalyzeSpcStudyInput extends AnalyzeSpcStudyBaseInput {
  /** 未指定時後端維持既有 variable 研究相容行為。 */
  analysis_family?: SpcAnalysisFamily;
  /** 屬性研究可傳 interval、chart_type 與受後端驗證的 alpha。 */
  options?: Record<string, unknown>;
}

export interface AnalyzeMachineSpcStudyInput extends Omit<AnalyzeSpcStudyBaseInput, 'source' | 'filters' | 'study_type'> {
  source: 'patrol';
  filters: MachineStudyFilters;
  analysis_family: 'machine';
  options: MachineStudyOptions;
}

type AnalyzeStudyRequest = AnalyzeSpcStudyInput | AnalyzeMachineSpcStudyInput;

export interface SpcStudyActionInput {
  versionId: number;
  studyId: number;
  reason: string;
}

export interface ConfirmSpcTimeModelInput extends SpcStudyActionInput {
  model: SpcTimeModelCode;
}

export interface ConfirmSpcTransformationInput extends SpcStudyActionInput {
  model: SpcTransformationModel;
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
    mutationFn: async (input: AnalyzeStudyRequest) => unwrap(
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

export const useConfirmSpcTransformation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ versionId, model, reason }: ConfirmSpcTransformationInput) => unwrap(
      await api.post<ApiSuccess<SpcStudyVersionSummary>>(
        `/spc/study-versions/${versionId}/transformation`, { model, reason },
      ),
    ),
    onSuccess: (_version, input) => invalidateStudy(queryClient, input.studyId),
  });
};

/** 核准機器研究結論；後端不會建立生產界限。 */
export const useApproveSpcResearch = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ versionId, reason }: SpcStudyActionInput) => unwrap(
      await api.post<ApiSuccess<SpcStudyVersionSummary>>(
        `/spc/study-versions/${versionId}/approve-research`, { reason },
      ),
    ),
    onSuccess: (_version, input) => invalidateStudy(queryClient, input.studyId),
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
