import { useMutation } from '@tanstack/react-query';
import toast from 'react-hot-toast';

import api from '../../services/api';
import { getReworkErrorMessage } from './reworkError';
import type { ReworkApplicationPayload } from './reworkFormPayload';

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

export const useCreateReworkApplication = ({ onSuccess }: ReworkMutationOptions = {}) =>
  useMutation({
    mutationFn: (payload: ReworkApplicationPayload) => api.post('/rework/apply', payload),
    onSuccess: () => handleSuccess('申請提交成功', onSuccess),
    onError: error => handleError(error, '申請失敗'),
  });

export const useApproveReworkApplication = ({ onSuccess }: ReworkMutationOptions = {}) =>
  useMutation({
    mutationFn: (payload: unknown) => api.post('/rework/approve', payload),
    onSuccess: () => handleSuccess('審核完成', onSuccess),
    onError: error => handleError(error, '審核失敗'),
  });

export const useUpdateReworkApplication = ({ onSuccess }: ReworkMutationOptions = {}) =>
  useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: unknown }) => api.put(`/rework/application/${id}`, payload),
    onSuccess: () => handleSuccess('基本資訊已更新', onSuccess),
    onError: error => handleError(error, '更新失敗'),
  });

export const useCreateReworkExecution = ({ onSuccess }: ReworkMutationOptions = {}) =>
  useMutation({
    mutationFn: (payload: unknown) => api.post('/rework/execute', payload),
    onSuccess: () => handleSuccess('執行記錄已新增', onSuccess),
    onError: error => handleError(error, '新增失敗'),
  });

export const useUpdateReworkExecution = ({ onSuccess }: ReworkMutationOptions = {}) =>
  useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: unknown }) => api.put(`/rework/execution/${id}`, payload),
    onSuccess: () => handleSuccess('執行記錄已更新', onSuccess),
    onError: error => handleError(error, '更新失敗'),
  });

export const useCreateReworkInspection = ({ onSuccess }: ReworkMutationOptions = {}) =>
  useMutation({
    mutationFn: (payload: unknown) => api.post('/rework/inspect', payload),
    onSuccess: () => handleSuccess('品檢記錄已新增', onSuccess),
    onError: error => handleError(error, '新增失敗'),
  });

export const useUpdateReworkInspection = ({ onSuccess }: ReworkMutationOptions = {}) =>
  useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: unknown }) => api.put(`/rework/inspection/${id}`, payload),
    onSuccess: () => handleSuccess('品檢記錄已更新', onSuccess),
    onError: error => handleError(error, '更新失敗'),
  });

export const useCreateReworkCost = ({ onSuccess }: ReworkMutationOptions = {}) =>
  useMutation({
    mutationFn: (payload: unknown) => api.post('/rework/cost', payload),
    onSuccess: () => handleSuccess('成本記錄已新增', onSuccess),
    onError: error => handleError(error, '新增失敗'),
  });

export const useUpdateReworkCost = ({ onSuccess }: ReworkMutationOptions = {}) =>
  useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: unknown }) => api.put(`/rework/cost/${id}`, payload),
    onSuccess: () => handleSuccess('成本記錄已更新', onSuccess),
    onError: error => handleError(error, '更新失敗'),
  });
