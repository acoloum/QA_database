import { useMutation, useQueryClient, type QueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';

import api from '../../services/api';
import { getReworkErrorMessage } from './reworkError';
import type {
  ReworkApplicationPayload,
  ReworkApplicationUpdatePayload,
  ReworkApprovalPayload,
  ReworkCostPayload,
  ReworkExecutionPayload,
  ReworkInspectionPayload,
} from './reworkFormPayload';

interface ReworkMutationOptions {
  onSuccess?: () => void;
}

const handleSuccess = (message: string, onSuccess?: () => void) => {
  toast.success(message);
  onSuccess?.();
};

const handleError = (error: unknown, fallback: string) => {
  toast.error(getReworkErrorMessage(error, fallback));
};

// 只讓 rework 列表與統計快取失效（精確 key），不用寬 prefix 清掉整個 rework 快取
const invalidateReworkListQueries = (queryClient: QueryClient) => {
  void queryClient.invalidateQueries({ queryKey: ['rework', 'applications'] });
  void queryClient.invalidateQueries({ queryKey: ['rework', 'statistics'] });
};

export const useCreateReworkApplication = ({ onSuccess }: ReworkMutationOptions = {}) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ReworkApplicationPayload) => api.post('/rework/apply', payload),
    onSuccess: () => {
      handleSuccess('申請提交成功', onSuccess);
      invalidateReworkListQueries(queryClient);
    },
    onError: error => handleError(error, '申請失敗'),
  });
};

export const useApproveReworkApplication = ({ onSuccess }: ReworkMutationOptions = {}) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ReworkApprovalPayload) => api.post('/rework/approve', payload),
    onSuccess: () => {
      handleSuccess('審核完成', onSuccess);
      invalidateReworkListQueries(queryClient);
    },
    onError: error => handleError(error, '審核失敗'),
  });
};

export const useUpdateReworkApplication = ({ onSuccess }: ReworkMutationOptions = {}) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: ReworkApplicationUpdatePayload }) => api.put(`/rework/application/${id}`, payload),
    onSuccess: () => {
      handleSuccess('基本資訊已更新', onSuccess);
      invalidateReworkListQueries(queryClient);
    },
    onError: error => handleError(error, '更新失敗'),
  });
};

export const useCreateReworkExecution = ({ onSuccess }: ReworkMutationOptions = {}) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ReworkExecutionPayload) => api.post('/rework/execute', payload),
    onSuccess: () => {
      handleSuccess('執行記錄已新增', onSuccess);
      invalidateReworkListQueries(queryClient);
    },
    onError: error => handleError(error, '新增失敗'),
  });
};

export const useUpdateReworkExecution = ({ onSuccess }: ReworkMutationOptions = {}) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: ReworkExecutionPayload }) => api.put(`/rework/execution/${id}`, payload),
    onSuccess: () => {
      handleSuccess('執行記錄已更新', onSuccess);
      invalidateReworkListQueries(queryClient);
    },
    onError: error => handleError(error, '更新失敗'),
  });
};

export const useCreateReworkInspection = ({ onSuccess }: ReworkMutationOptions = {}) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ReworkInspectionPayload) => api.post('/rework/inspect', payload),
    onSuccess: () => {
      handleSuccess('品檢記錄已新增', onSuccess);
      invalidateReworkListQueries(queryClient);
    },
    onError: error => handleError(error, '新增失敗'),
  });
};

export const useUpdateReworkInspection = ({ onSuccess }: ReworkMutationOptions = {}) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: ReworkInspectionPayload }) => api.put(`/rework/inspection/${id}`, payload),
    onSuccess: () => {
      handleSuccess('品檢記錄已更新', onSuccess);
      invalidateReworkListQueries(queryClient);
    },
    onError: error => handleError(error, '更新失敗'),
  });
};

export const useCreateReworkCost = ({ onSuccess }: ReworkMutationOptions = {}) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ReworkCostPayload) => api.post('/rework/cost', payload),
    onSuccess: () => {
      handleSuccess('成本記錄已新增', onSuccess);
      invalidateReworkListQueries(queryClient);
    },
    onError: error => handleError(error, '新增失敗'),
  });
};

export const useUpdateReworkCost = ({ onSuccess }: ReworkMutationOptions = {}) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: ReworkCostPayload }) => api.put(`/rework/cost/${id}`, payload),
    onSuccess: () => {
      handleSuccess('成本記錄已更新', onSuccess);
      invalidateReworkListQueries(queryClient);
    },
    onError: error => handleError(error, '更新失敗'),
  });
};
