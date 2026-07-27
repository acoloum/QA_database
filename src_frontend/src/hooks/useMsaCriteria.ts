import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import api from '../services/api';
import type {
  ApproveMsaCriteriaVersionInput,
  CreateMsaCriteriaProfileInput,
  CreateMsaCriteriaVersionInput,
  MsaCriteriaListParams,
  MsaCriteriaProfile,
  MsaCriteriaVersion,
  MsaPage,
} from '../types/msa';
import { msaKeys } from './useMsaEquipment';

interface ApiEnvelope<T> {
  data: T;
}

const unwrap = <T,>(response: { data: ApiEnvelope<T> }): T => response.data.data;

const criteriaListKey = (params: MsaCriteriaListParams) => [
  ...msaKeys.criteria(), 'list', params,
] as const;

export const useMsaCriteria = (params: MsaCriteriaListParams) => useQuery({
  queryKey: criteriaListKey(params),
  queryFn: async () => unwrap(
    await api.get<ApiEnvelope<MsaPage<MsaCriteriaProfile>>>('/msa/criteria', { params }),
  ),
});

export const useCreateMsaCriteriaProfile = () => {
  const queryClient = useQueryClient();
  return useMutation<MsaCriteriaProfile, unknown, CreateMsaCriteriaProfileInput>({
    mutationFn: async (payload: CreateMsaCriteriaProfileInput) => unwrap(
      await api.post<ApiEnvelope<MsaCriteriaProfile>>('/msa/criteria', payload),
    ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: msaKeys.criteria() }),
  });
};

export const useCreateMsaCriteriaVersion = () => {
  const queryClient = useQueryClient();
  return useMutation<MsaCriteriaVersion, unknown, CreateMsaCriteriaVersionInput>({
    mutationFn: async ({ profileId, ...payload }: CreateMsaCriteriaVersionInput) => unwrap(
      await api.post<ApiEnvelope<MsaCriteriaVersion>>(`/msa/criteria/${profileId}/versions`, payload),
    ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: msaKeys.criteria() }),
  });
};

export const useApproveMsaCriteriaVersion = () => {
  const queryClient = useQueryClient();
  return useMutation<MsaCriteriaVersion, unknown, ApproveMsaCriteriaVersionInput>({
    mutationFn: async ({ versionId, ...payload }: ApproveMsaCriteriaVersionInput) => unwrap(
      await api.post<ApiEnvelope<MsaCriteriaVersion>>(`/msa/criteria/versions/${versionId}/approve`, payload),
    ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: msaKeys.criteria() }),
  });
};
