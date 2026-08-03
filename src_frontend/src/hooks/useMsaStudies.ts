import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import api, { unwrap, type ApiEnvelope } from '../services/api';
import { downloadResponseBlob } from '../utils/downloadFile';
import type {
  CorrectMsaObservationInput,
  CreateMsaPlanInput,
  CreateMsaStudyInput,
  MsaBlindTask,
  MsaCompletenessReport,
  MsaObservation,
  MsaObservationImportBatch,
  MsaPage,
  MsaPlanVersion,
  MsaRestudyRequest,
  MsaResultVersion,
  MsaStudy,
  MsaStudyListParams,
  MsaWorkflowActionInput,
  RecordMsaObservationInput,
  UpdateMsaStudyInput,
} from '../types/msa';
import { msaKeys } from './useMsaEquipment';

// 子樹 prefix：既給下面的 key 組合用，也給 invalidate 用，
// 兩邊共用同一份定義才不會一邊改了另一邊失效。
const studiesPrefix     = [...msaKeys.all, 'studies'] as const;
const studyPrefix       = [...msaKeys.all, 'study'] as const;
const tasksPrefix       = [...msaKeys.all, 'plan-tasks'] as const;
const observationPrefix = [...msaKeys.all, 'plan-observations'] as const;
const restudyPrefix     = [...msaKeys.all, 'restudy-requests'] as const;

export const msaStudyKeys = {
  lists: () => studiesPrefix,
  list: (params: MsaStudyListParams) =>
    [...studiesPrefix, params] as const,
  details: () => studyPrefix,
  detail: (studyId: number) =>
    [...studyPrefix, studyId] as const,
  allTasks: () => tasksPrefix,
  tasks: (planId: number) =>
    [...tasksPrefix, planId] as const,
  allObservations: () => observationPrefix,
  observations: (planId: number) =>
    [...observationPrefix, planId] as const,
  restudy: () => restudyPrefix,
};

/**
 * 研究領域 mutation 後統一刷新「研究」相關快取。
 * 刻意以子樹 prefix 取代 msaKeys.all（['msa']），排除 equipment / criteria /
 * import 等獨立資料域——那些由各自 mutation 負責刷新，
 * 避免一次研究操作連帶觸發全部 MSA 資料重新抓取。
 * v5 invalidateQueries 只會重新抓取目前 active 的 query。
 */
const invalidateMsaStudyDomain = (queryClient: ReturnType<typeof useQueryClient>) => {
  queryClient.invalidateQueries({ queryKey: msaStudyKeys.lists() });
  queryClient.invalidateQueries({ queryKey: msaStudyKeys.details() });
  queryClient.invalidateQueries({ queryKey: msaStudyKeys.allTasks() });
  queryClient.invalidateQueries({ queryKey: msaStudyKeys.allObservations() });
  queryClient.invalidateQueries({ queryKey: msaStudyKeys.restudy() });
};

// ---------------------------------------------------------------------------
// 研究
// ---------------------------------------------------------------------------

export const useMsaStudies = (params: MsaStudyListParams) => useQuery({
  queryKey: msaStudyKeys.list(params),
  queryFn: async () => unwrap(
    await api.get<ApiEnvelope<MsaPage<MsaStudy>>>('/msa/studies', { params }),
  ),
});

export const useMsaStudy = (studyId: number | null) => useQuery({
  queryKey: msaStudyKeys.detail(studyId ?? 0),
  enabled: studyId != null,
  queryFn: async () => unwrap(
    await api.get<ApiEnvelope<MsaStudy>>(`/msa/studies/${studyId}`),
  ),
});

export const useCreateMsaStudy = () => {
  const queryClient = useQueryClient();
  return useMutation<MsaStudy, unknown, CreateMsaStudyInput>({
    mutationFn: async (payload) => unwrap(
      await api.post<ApiEnvelope<MsaStudy>>('/msa/studies', payload),
    ),
    onSuccess: () => invalidateMsaStudyDomain(queryClient),
  });
};

export const useUpdateMsaStudy = () => {
  const queryClient = useQueryClient();
  return useMutation<MsaStudy, unknown, UpdateMsaStudyInput>({
    mutationFn: async ({ studyId, ...payload }) => unwrap(
      await api.patch<ApiEnvelope<MsaStudy>>(
        `/msa/studies/${studyId}`, payload,
      ),
    ),
    onSuccess: () => invalidateMsaStudyDomain(queryClient),
  });
};

// ---------------------------------------------------------------------------
// 計畫與凍結
// ---------------------------------------------------------------------------

export const useCreateMsaPlan = () => {
  const queryClient = useQueryClient();
  return useMutation<MsaPlanVersion, unknown, CreateMsaPlanInput>({
    mutationFn: async ({ studyId, ...payload }) => unwrap(
      await api.post<ApiEnvelope<MsaPlanVersion>>(
        `/msa/studies/${studyId}/plans`, payload,
      ),
    ),
    onSuccess: () => invalidateMsaStudyDomain(queryClient),
  });
};

export const useFreezeMsaPlan = () => {
  const queryClient = useQueryClient();
  return useMutation<
    MsaPlanVersion, unknown, { planId: number; expected_plan_hash?: string }
  >({
    mutationFn: async ({ planId, ...payload }) => unwrap(
      await api.post<ApiEnvelope<MsaPlanVersion>>(
        `/msa/plans/${planId}/freeze`, payload,
      ),
    ),
    onSuccess: () => invalidateMsaStudyDomain(queryClient),
  });
};

export const useMsaPlanTasks = (planId: number | null) => useQuery({
  queryKey: msaStudyKeys.tasks(planId ?? 0),
  enabled: planId != null,
  queryFn: async () => unwrap(
    await api.get<ApiEnvelope<{ items: MsaBlindTask[] }>>(
      `/msa/plans/${planId}/tasks`,
    ),
  ),
});

// ---------------------------------------------------------------------------
// 觀測
// ---------------------------------------------------------------------------

/** 管理用觀測視圖，含已作廢紀錄；需要 msa.manage。 */
export const useMsaPlanObservations = (planId: number | null, enabled = true) =>
  useQuery({
    queryKey: msaStudyKeys.observations(planId ?? 0),
    enabled: planId != null && enabled,
    queryFn: async () => unwrap(
      await api.get<ApiEnvelope<{ items: MsaObservation[] }>>(
        `/msa/plans/${planId}/observations`,
      ),
    ),
  });

export const useRecordMsaObservation = () => {
  const queryClient = useQueryClient();
  return useMutation<MsaObservation, unknown, RecordMsaObservationInput>({
    mutationFn: async ({ planId, ...payload }) => unwrap(
      await api.post<ApiEnvelope<MsaObservation>>(
        `/msa/plans/${planId}/observations`, payload,
      ),
    ),
    onSuccess: (_data, variables) => queryClient.invalidateQueries({
      queryKey: msaStudyKeys.tasks(variables.planId),
    }),
  });
};

export const useCorrectMsaObservation = () => {
  const queryClient = useQueryClient();
  return useMutation<MsaObservation, unknown, CorrectMsaObservationInput>({
    mutationFn: async ({ observationId, ...payload }) => unwrap(
      await api.post<ApiEnvelope<MsaObservation>>(
        `/msa/observations/${observationId}/corrections`, payload,
      ),
    ),
    onSuccess: () => invalidateMsaStudyDomain(queryClient),
  });
};

export const useValidateMsaPlan = () => {
  const queryClient = useQueryClient();
  return useMutation<MsaCompletenessReport, unknown, { planId: number }>({
    mutationFn: async ({ planId }) => unwrap(
      await api.post<ApiEnvelope<MsaCompletenessReport>>(
        `/msa/plans/${planId}/validate`, {},
      ),
    ),
    onSuccess: () => invalidateMsaStudyDomain(queryClient),
  });
};

export const usePreviewMsaObservationImport = () => useMutation<
  MsaObservationImportBatch, unknown, { planId: number; file: File }
>({
  mutationFn: async ({ planId, file }) => {
    const form = new FormData();
    form.append('file', file);
    return unwrap(
      await api.post<ApiEnvelope<MsaObservationImportBatch>>(
        `/msa/plans/${planId}/imports/preview`, form,
      ),
    );
  },
});

export const useConfirmMsaObservationImport = () => {
  const queryClient = useQueryClient();
  return useMutation<
    MsaObservationImportBatch, unknown, { planId: number; batchId: number }
  >({
    mutationFn: async ({ planId, batchId }) => unwrap(
      await api.post<ApiEnvelope<MsaObservationImportBatch>>(
        `/msa/plans/${planId}/imports/${batchId}/confirm`, {},
      ),
    ),
    onSuccess: () => invalidateMsaStudyDomain(queryClient),
  });
};

// ---------------------------------------------------------------------------
// 分析與工作流
// ---------------------------------------------------------------------------

export const useAnalyzeMsaPlan = () => {
  const queryClient = useQueryClient();
  return useMutation<
    MsaResultVersion, unknown, { planId: number; expected_plan_hash?: string }
  >({
    mutationFn: async ({ planId, ...payload }) => unwrap(
      await api.post<ApiEnvelope<MsaResultVersion>>(
        `/msa/plans/${planId}/analyze`, payload,
      ),
    ),
    onSuccess: () => invalidateMsaStudyDomain(queryClient),
  });
};

type WorkflowAction = 'submit' | 'approve' | 'reject' | 'void';

const workflowRequest = (action: WorkflowAction) =>
  async ({ resultId, ...payload }: MsaWorkflowActionInput) => unwrap(
    await api.post<ApiEnvelope<MsaResultVersion>>(
      `/msa/results/${resultId}/${action}`, payload,
    ),
  );

export const useSubmitMsaResult = () => {
  const queryClient = useQueryClient();
  return useMutation<MsaResultVersion, unknown, MsaWorkflowActionInput>({
    mutationFn: workflowRequest('submit'),
    onSuccess: () => invalidateMsaStudyDomain(queryClient),
  });
};

export const useApproveMsaResult = () => {
  const queryClient = useQueryClient();
  return useMutation<MsaResultVersion, unknown, MsaWorkflowActionInput>({
    mutationFn: workflowRequest('approve'),
    onSuccess: () => invalidateMsaStudyDomain(queryClient),
  });
};

export const useRejectMsaResult = () => {
  const queryClient = useQueryClient();
  return useMutation<MsaResultVersion, unknown, MsaWorkflowActionInput>({
    mutationFn: workflowRequest('reject'),
    onSuccess: () => invalidateMsaStudyDomain(queryClient),
  });
};

export const useVoidMsaResult = () => {
  const queryClient = useQueryClient();
  return useMutation<MsaResultVersion, unknown, MsaWorkflowActionInput>({
    mutationFn: workflowRequest('void'),
    onSuccess: () => invalidateMsaStudyDomain(queryClient),
  });
};

// ---------------------------------------------------------------------------
// 再研究
// ---------------------------------------------------------------------------

export const useMsaRestudyRequests = (
  params: { page: number; page_size: number; status?: string } = {
    page: 1, page_size: 25,
  },
) => useQuery({
  queryKey: [...msaStudyKeys.restudy(), params] as const,
  queryFn: async () => unwrap(
    await api.get<ApiEnvelope<MsaPage<MsaRestudyRequest>>>(
      '/msa/restudy-requests', { params },
    ),
  ),
});

export const useStartMsaRestudy = () => {
  const queryClient = useQueryClient();
  return useMutation<MsaRestudyRequest, unknown, { requestId: number }>({
    mutationFn: async ({ requestId }) => unwrap(
      await api.post<ApiEnvelope<MsaRestudyRequest>>(
        `/msa/restudy-requests/${requestId}/start`, {},
      ),
    ),
    onSuccess: () => invalidateMsaStudyDomain(queryClient),
  });
};

// ---------------------------------------------------------------------------
// 報告下載
// ---------------------------------------------------------------------------

const REPORT_MIME = {
  xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  pdf: 'application/pdf',
} as const;

/**
 * 報告一律經共用 axios 實例下載，才會帶上 JWT 並套用統一錯誤處理。
 */
export const useDownloadMsaReport = () => useMutation<
  void, unknown, { resultId: number; format: 'xlsx' | 'pdf'; studyNo?: string }
>({
  mutationFn: async ({ resultId, format, studyNo }) => {
    const response = await api.get<Blob>(
      `/msa/results/${resultId}/report.${format}`,
      { responseType: 'blob' },
    );
    const name = studyNo ? `MSA_${studyNo}_v${resultId}` : `MSA_${resultId}`;
    downloadResponseBlob(response.data, `${name}.${format}`, REPORT_MIME[format]);
  },
});
